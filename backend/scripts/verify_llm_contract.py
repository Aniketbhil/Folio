#!/usr/bin/env python3
"""Regression test verifying LLM contract signatures and live-mode execution.

Patches the underlying google-genai provider call with a fake returning valid
schema-conforming JSON, forces LLM_MOCK=false, and verifies that the tutor
answer path, KB build, quiz generation + verification, short-answer grading,
and misconception summary all succeed without signature or schema mismatches.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure fresh isolated environment BEFORE importing app modules
TEMP_DIR = tempfile.mkdtemp(prefix="folio_llm_contract_")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DIR}/test.db"
os.environ["CHROMA_DIR"] = f"{TEMP_DIR}/chroma"
os.environ["UPLOAD_DIR"] = f"{TEMP_DIR}/uploads"
os.environ["LLM_MOCK"] = "false"
os.environ["GEMINI_API_KEY"] = "fake_contract_test_key"
os.environ["DEBUG"] = "true"
os.environ["AUTO_BUILD_KB"] = "false"
os.environ["LLM_TIMEOUT_SEC"] = "60"
os.environ["AUTH_REQUIRED"] = "false"

Path(f"{TEMP_DIR}/chroma").mkdir(parents=True, exist_ok=True)
Path(f"{TEMP_DIR}/uploads").mkdir(parents=True, exist_ok=True)

from sqlalchemy import func, select
from app.core.config import get_settings
from app.db.session import Base, SessionLocal, engine
from app.models.assessment import Assessment, Attempt, Question
from app.models.conversation import Conversation
from app.models.course import Course
from app.models.source import Chunk, Source
from app.models.student import Student
from app.models.topic import ChunkTopic, Topic
from app.services.assessment.generator import LiveQuestionGenerator
from app.services.assessment.reporting import generate_misconception_summary
from app.services.assessment.schemas import (
    GeneratedQuestionLLM,
    QuestionVerificationItemLLM,
    TopicGenerationLLMOutput,
    TopicVerificationLLMOutput,
)
from app.services.assessment.selection import TopicContext
from app.services.assessment.verifier import LiveQuestionVerifier
from app.services.grading.grader import GradingService
from app.services.grading.schemas import (
    MisconceptionSummary,
    MisconceptionSummaryItem,
    ShortAnswerGrade,
    WrongAnswerDiagnosis,
)
from app.services.kb.builder import build_knowledge_base
from app.services.kb.schemas import (
    CandidateTopic,
    ChunkTagItem,
    ChunkTopicAssignment,
    MapTopicsOutput,
    SubtopicOutput,
    TagBatchOutput,
    TaxonomyOutput,
    TopTopicOutput,
)
from app.services.llm import LLMClient, get_llm_client
from app.services.tutor.schemas import TutorLLMOutput
from app.services.tutor.service import get_tutor_service
from app.services.vector_store import get_vector_store


def fake_generate_content(*args, **kwargs):
    """Fake Gemini generate_content returning valid schema JSON for any Pydantic schema."""
    config = kwargs.get("config")
    schema = getattr(config, "response_schema", None) if config else None
    res = MagicMock()

    if schema is not None:
        if schema is TutorLLMOutput:
            inst = TutorLLMOutput(
                grounding="grounded",
                answer="According to [1], an object stays at rest unless a net external force acts on it.",
                used_sources=[1],
                outside_knowledge_note=None,
                followups=["What is Newton's third law?"],
            )
        elif schema is MapTopicsOutput:
            inst = MapTopicsOutput(
                topics=[
                    CandidateTopic(
                        name="Newtonian Mechanics", description="Laws of motion and force"
                    )
                ]
            )
        elif schema is TaxonomyOutput:
            inst = TaxonomyOutput(
                topics=[
                    TopTopicOutput(
                        name="Classical Mechanics",
                        description="Study of motion and forces",
                        subtopics=[
                            SubtopicOutput(
                                name="Newton's Laws",
                                description="Core laws of motion",
                                prerequisites=[],
                            )
                        ],
                    )
                ]
            )
        elif schema is TagBatchOutput:
            # Match chunk ID dynamically from prompt or use 1
            prompt_str = kwargs.get("contents", "")
            chunk_id = 1
            if "Chunk ID: " in str(prompt_str):
                try:
                    chunk_id = int(str(prompt_str).split("Chunk ID: ")[1].split("\n")[0].strip())
                except Exception:
                    chunk_id = 1

            inst = TagBatchOutput(
                chunks=[
                    ChunkTagItem(
                        chunk_id=chunk_id,
                        topics=[
                            ChunkTopicAssignment(name="Newton's Laws", relevance=1.0)
                        ],
                        concepts=[],
                    )
                ]
            )
        elif schema is TopicGenerationLLMOutput:
            inst = TopicGenerationLLMOutput(
                questions=[
                    GeneratedQuestionLLM(
                        qtype="short_answer",
                        difficulty="medium",
                        prompt="What is force according to Newton's second law?",
                        model_answer="Force equals mass times acceleration (F=ma)",
                        key_points=["Mentions mass", "Mentions acceleration"],
                        explanation="F=ma defines force.",
                        used_sources=[1],
                    )
                ]
            )
        elif schema is TopicVerificationLLMOutput:
            inst = TopicVerificationLLMOutput(
                results=[
                    QuestionVerificationItemLLM(
                        question_index=0,
                        supported=True,
                        key_correct=True,
                        ambiguous=False,
                        notes="Question is fully grounded.",
                    )
                ]
            )
        elif schema is ShortAnswerGrade:
            inst = ShortAnswerGrade(
                score=1.0,
                feedback="Completely accurate definition.",
                key_points_hit=["mass", "acceleration"],
                key_points_missing=[],
            )
        elif schema is MisconceptionSummary:
            inst = MisconceptionSummary(
                items=[
                    MisconceptionSummaryItem(
                        topic_id=1,
                        text="Believing heavier objects accelerate faster under gravity",
                        count=2,
                    )
                ]
            )
        elif schema is WrongAnswerDiagnosis:
            inst = WrongAnswerDiagnosis(
                misconception="Assumed terminal velocity without air resistance",
                feedback="In a vacuum, all objects fall at the same rate.",
            )
        else:
            dummy_llm = LLMClient(get_settings())
            inst = dummy_llm._build_mock_instance(schema)

        res.text = inst.model_dump_json()
    else:
        res.text = "Newtonian mechanics is the study of motion."

    return res


def fake_embed_content(*args, **kwargs):
    """Fake Gemini embed_content returning 64-dim unit vectors."""
    contents = kwargs.get("contents")
    if contents is None and args:
        contents = args[0]
    if contents is None:
        contents = []

    res = MagicMock()
    unit_vec = [1.0] + [0.0] * 63
    res.embeddings = [MagicMock(values=unit_vec) for _ in contents]
    return res


def run_contract_verification() -> int:
    print("=" * 75)
    print(" Folio LLM Contract & Live Mode Regression Verification")
    print("=" * 75)
    settings = get_settings()
    print(f"Isolated temp DB:       {os.environ['DATABASE_URL']}")
    print(f"Isolated Chroma store: {os.environ['CHROMA_DIR']}")
    print(f"Isolated Uploads dir:  {os.environ['UPLOAD_DIR']}")
    print(f"LLM_MOCK setting:      {settings.llm_mock} (expected False)")
    print(f"LLM_TIMEOUT_SEC:       {settings.llm_timeout_sec}s (read from settings)")
    print("-" * 75)

    assert not settings.llm_mock, "Test must run with LLM_MOCK=false to verify live contract!"

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Setup fake provider mock client
    mock_genai_client = MagicMock()
    mock_genai_client.models.generate_content.side_effect = fake_generate_content
    mock_genai_client.models.embed_content.side_effect = fake_embed_content

    results = {}

    with patch("google.genai.Client", return_value=mock_genai_client):
        # Clear lru_cache for get_llm_client to ensure it picks up patched genai.Client
        get_llm_client.cache_clear()
        llm = get_llm_client()
        vstore = get_vector_store()

        with SessionLocal() as db:
            # Seed base fixture
            student = Student(name="Contract Student")
            db.add(student)
            db.flush()

            course = Course(name="Contract Physics", kb_status="ready")
            db.add(course)
            db.flush()

            source = Source(
                course_id=course.id,
                title="Mechanics Handbook",
                source_type="pdf",
                original_filename="handbook.pdf",
                file_path="handbook.pdf",
                status="ready",
            )
            db.add(source)
            db.flush()

            chunk = Chunk(
                course_id=course.id,
                source_id=source.id,
                chunk_index=0,
                text="Newton's first law states that an object remains at rest unless acted on by an external force.",
                source_type="pdf",
                embedded=True,
            )
            db.add(chunk)
            db.flush()

            topic = Topic(course_id=course.id, name="Newton's Laws", description="Core motion laws")
            db.add(topic)
            db.flush()

            ct = ChunkTopic(chunk_id=chunk.id, topic_id=topic.id, relevance=1.0)
            db.add(ct)
            db.commit()
            db.refresh(student)
            db.refresh(course)
            db.refresh(source)
            db.refresh(chunk)
            db.refresh(topic)

            vstore.add_chunks([
                {
                    "chunk_id": chunk.id,
                    "course_id": course.id,
                    "source_id": source.id,
                    "text": chunk.text,
                    "embedding": [1.0] + [0.0] * 63,
                    "topic_id": topic.id,
                }
            ])

            # -------------------------------------------------------------
            # Path 1: Tutor Answer Path (Live Mode)
            # -------------------------------------------------------------
            print("--> Testing Path 1: Tutor Answer Path (Live Mode)...", end=" ")
            try:
                conv = Conversation(
                    course_id=course.id, student_id=student.id, title="Contract Conversation"
                )
                db.add(conv)
                db.commit()
                db.refresh(conv)

                tutor_svc = get_tutor_service()
                resp = tutor_svc.answer(
                    db=db,
                    conversation=conv,
                    student_id=student.id,
                    content="Explain Newton's first law",
                )

                assert resp.answer, "Tutor response answer is empty"
                assert resp.grounding == "grounded", f"Expected grounded, got {resp.grounding}"
                assert len(resp.citations) >= 1, "Expected at least 1 citation"
                print("PASS")
                results["tutor_answer"] = True
            except Exception as e:
                print(f"FAIL: {e}")
                results["tutor_answer"] = False

            # -------------------------------------------------------------
            # Path 2: Knowledge Base Build (Live Mode Map/Reduce/Tag)
            # -------------------------------------------------------------
            print("--> Testing Path 2: KB Build on small fixture (Live Mode)...", end=" ")
            try:
                kb_course = Course(
                    name="KB Test Course", kb_status="pending"
                )
                db.add(kb_course)
                db.flush()

                kb_source = Source(
                    course_id=kb_course.id,
                    title="Dynamics Notes",
                    source_type="pdf",
                    original_filename="notes.pdf",
                    file_path="notes.pdf",
                    status="ready",
                )
                db.add(kb_source)
                db.flush()

                kb_chunk = Chunk(
                    course_id=kb_course.id,
                    source_id=kb_source.id,
                    chunk_index=0,
                    text="Inertial reference frames and Newton's laws of classical motion.",
                    source_type="pdf",
                    embedded=True,
                )
                db.add(kb_chunk)
                db.commit()
                db.refresh(kb_course)
                db.refresh(kb_chunk)

                vstore.add_chunks([
                    {
                        "chunk_id": kb_chunk.id,
                        "course_id": kb_course.id,
                        "source_id": kb_source.id,
                        "text": kb_chunk.text,
                        "embedding": [1.0] + [0.0] * 63,
                    }
                ])

                build_knowledge_base(kb_course.id)
                db.refresh(kb_course)

                assert kb_course.kb_status == "ready", f"KB status is {kb_course.kb_status}"
                topic_count = db.scalar(
                    select(func.count(Topic.id)).where(Topic.course_id == kb_course.id)
                )
                assert topic_count and topic_count > 0, "No topics created by KB builder"
                print("PASS")
                results["kb_build"] = True
            except Exception as e:
                print(f"FAIL: {e}")
                results["kb_build"] = False

            # -------------------------------------------------------------
            # Path 3: Quiz Generation plus Verification (Live Mode)
            # -------------------------------------------------------------
            print("--> Testing Path 3: Quiz Generation + Verification (Live Mode)...", end=" ")
            try:
                generator = LiveQuestionGenerator(llm)
                verifier = LiveQuestionVerifier(llm)

                ctx = TopicContext(
                    topic=topic,
                    parent_topic=None,
                    concepts=[],
                    chunks=[chunk],
                    source_map={source.id: source},
                    chunk_citations=[{"location": "Page 1", "snippet": chunk.text[:80]}],
                    requested_count=1,
                    assigned_qtypes=["short_answer"],
                    assigned_difficulties=["medium"],
                    has_numerical_support=False,
                )

                candidates = generator.generate_for_topic(ctx, do_not_repeat_prompts=[], seed=42)
                assert len(candidates) > 0, "Question generator produced 0 candidates"

                all_chunks_map = {chunk.id: chunk}
                passed, rejected = verifier.verify_candidates(candidates, all_chunks_map)
                assert len(passed) > 0, "Question verifier accepted 0 candidates"
                assert passed[0].prompt, "Candidate question prompt is empty"
                print("PASS")
                results["quiz_gen_verify"] = True
            except Exception as e:
                print(f"FAIL: {e}")
                results["quiz_gen_verify"] = False

            # Create assessment for question fixtures
            assessment = Assessment(
                course_id=course.id,
                student_id=student.id,
                kind="quiz",
                title="Regression Assessment",
                status="completed",
            )
            db.add(assessment)
            db.commit()
            db.refresh(assessment)

            # -------------------------------------------------------------
            # Path 4: Short-Answer Grading (Live Mode)
            # -------------------------------------------------------------
            print("--> Testing Path 4: Short-Answer Grading (Live Mode)...", end=" ")
            try:
                grader = GradingService(llm=llm)
                sa_question = Question(
                    assessment_id=assessment.id,
                    course_id=course.id,
                    topic_id=topic.id,
                    qtype="short_answer",
                    prompt="What is force according to Newton's second law?",
                    options=[],
                    correct_answer="Force equals mass times acceleration (F=ma)",
                    explanation="Newton's second law specifies F=ma.",
                    difficulty="medium",
                    fingerprint="fp_sa_contract_1",
                    source_chunk_ids=[chunk.id],
                    position=1,
                )
                db.add(sa_question)
                db.commit()
                db.refresh(sa_question)

                grade_res = grader.grade(
                    question=sa_question,
                    answer="Force equals mass times acceleration.",
                    chunks=[chunk],
                    source_map={source.id: source},
                )

                assert grade_res.graded_by == "llm", f"Graded by {grade_res.graded_by}, expected 'llm'"
                assert grade_res.is_correct is True, "Expected correct grade"
                assert grade_res.score == 1.0, f"Expected score 1.0, got {grade_res.score}"
                print("PASS")
                results["short_answer_grading"] = True
            except Exception as e:
                print(f"FAIL: {e}")
                results["short_answer_grading"] = False

            # -------------------------------------------------------------
            # Path 5: Misconception Summary (Live Mode)
            # -------------------------------------------------------------
            print("--> Testing Path 5: Misconception Summary (Live Mode)...", end=" ")
            try:
                q2 = Question(
                    assessment_id=assessment.id,
                    course_id=course.id,
                    topic_id=topic.id,
                    qtype="short_answer",
                    prompt="Do heavier objects fall faster in vacuum?",
                    options=[],
                    correct_answer="No, all accelerate equally.",
                    explanation="g is constant in vacuum.",
                    difficulty="medium",
                    fingerprint="fp_sa_contract_2",
                    source_chunk_ids=[chunk.id],
                    position=2,
                )
                db.add(q2)
                db.commit()
                db.refresh(q2)

                att1 = Attempt(
                    assessment_id=assessment.id,
                    question_id=sa_question.id,
                    student_id=student.id,
                    answer="Force is energy times speed",
                    is_correct=False,
                    score=0.0,
                    feedback="Incorrect definition.",
                    misconception="Confuses force with kinetic energy",
                )
                att2 = Attempt(
                    assessment_id=assessment.id,
                    question_id=q2.id,
                    student_id=student.id,
                    answer="Yes heavier falls faster",
                    is_correct=False,
                    score=0.0,
                    feedback="Incorrect assumption.",
                    misconception="Believes mass determines free fall speed",
                )
                db.add_all([att1, att2])
                db.commit()

                topic_map = {topic.id: topic}
                summary = generate_misconception_summary(
                    llm=llm,
                    attempts=[att1, att2],
                    questions=[sa_question, q2],
                    topic_map=topic_map,
                )

                assert len(summary) > 0, "Misconception summary returned 0 items"
                assert "text" in summary[0], "Misconception item missing 'text'"
                print("PASS")
                results["misconception_summary"] = True
            except Exception as e:
                print(f"FAIL: {e}")
                results["misconception_summary"] = False

    print("-" * 75)
    all_passed = all(results.values()) and len(results) == 5
    print(f"Summary: {sum(results.values())}/5 paths PASSED")
    if all_passed:
        print("[RESULT] PASS: All live LLM contracts verified successfully!")
        return 0
    else:
        print("[RESULT] FAIL: One or more live LLM contract paths failed.")
        return 1


if __name__ == "__main__":
    sys.exit(run_contract_verification())
