from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.schemas.dev import (
    EmbedTestRequest,
    EmbedTestResponse,
    LLMTestRequest,
    LLMTestResponse,
    VectorTestResultItem,
    VectorTestResponse,
)
from app.services.llm import LLMClient, get_llm_client
from app.services.vector_store import VectorStore, get_vector_store

router = APIRouter(prefix="/dev", tags=["Developer"])


@router.post("/llm-test", response_model=LLMTestResponse)
def test_llm(
    payload: LLMTestRequest,
    llm: LLMClient = Depends(get_llm_client),
) -> LLMTestResponse:
    """Test LLM generation in current mode (mock or live)."""
    settings = get_settings()
    mode = "mock" if settings.llm_mock else "live"
    output = llm.generate_text(payload.prompt)
    return LLMTestResponse(mode=mode, output=output)


@router.post("/embed-test", response_model=EmbedTestResponse)
def test_embed(
    payload: EmbedTestRequest,
    llm: LLMClient = Depends(get_llm_client),
) -> EmbedTestResponse:
    """Test embedding generation dimensions and count."""
    embeddings = llm.embed_texts(payload.texts, task="document")
    dim = len(embeddings[0]) if embeddings else 0
    return EmbedTestResponse(dim=dim, count=len(embeddings))


@router.post("/vector-test", response_model=VectorTestResponse)
def test_vector(
    llm: LLMClient = Depends(get_llm_client),
    vector_store: VectorStore = Depends(get_vector_store),
) -> VectorTestResponse:
    """Insert 3 test chunks under temp course 0, run query, verify, and clean up."""
    temp_course_id = 0
    docs = [
        "Photosynthesis is the process by which green plants convert light into chemical energy.",
        "Cellular respiration produces ATP by breaking down glucose.",
        "Newton's second law states that Force equals mass times acceleration.",
    ]
    doc_embeddings = llm.embed_texts(docs, task="document")

    fake_chunks = [
        {
            "chunk_id": 99901,
            "course_id": temp_course_id,
            "source_id": 999,
            "text": docs[0],
            "embedding": doc_embeddings[0],
            "topic_id": 1,
        },
        {
            "chunk_id": 99902,
            "course_id": temp_course_id,
            "source_id": 999,
            "text": docs[1],
            "embedding": doc_embeddings[1],
            "topic_id": 1,
        },
        {
            "chunk_id": 99903,
            "course_id": temp_course_id,
            "source_id": 999,
            "text": docs[2],
            "embedding": doc_embeddings[2],
            "topic_id": 2,
        },
    ]

    vector_store.add_chunks(fake_chunks)

    query_text = "How do green plants capture light energy?"
    query_emb = llm.embed_texts([query_text], task="query")[0]
    query_results = vector_store.query_chunks(
        course_id=temp_course_id, query_embedding=query_emb, top_k=3
    )

    # Clean up temporary test data
    vector_store.delete_by_course(temp_course_id)

    return VectorTestResponse(
        success=True,
        queried_chunks=[
            VectorTestResultItem(
                chunk_id=res["chunk_id"],
                score=res["score"],
                distance=res["distance"],
            )
            for res in query_results
        ],
        cleaned_up=True,
    )
