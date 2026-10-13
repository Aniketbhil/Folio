import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


from app.core.errors import AppError


class VectorStore:
    """Wrapper for persistent Chroma vector database with cosine distance."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        chroma_path = Path(settings.chroma_dir)
        chroma_path.mkdir(parents=True, exist_ok=True)

        self._client: ClientAPI = chromadb.PersistentClient(path=str(chroma_path))
        self._chunks_col: Collection = self._client.get_or_create_collection(
            name="folio_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        self._questions_col: Collection = self._client.get_or_create_collection(
            name="folio_questions",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "VectorStore initialized at %s with collections: folio_chunks (%d), folio_questions (%d)",
            chroma_path,
            self._chunks_col.count(),
            self._questions_col.count(),
        )

    @property
    def chunks_collection(self) -> Collection:
        """Accessor for chunks collection."""
        return self._chunks_col

    @property
    def questions_collection(self) -> Collection:
        """Accessor for questions collection."""
        return self._questions_col

    def reset_collections(self) -> Dict[str, Any]:
        """Drop and recreate both Chroma collections."""
        try:
            self._client.delete_collection("folio_chunks")
        except Exception:
            pass
        try:
            self._client.delete_collection("folio_questions")
        except Exception:
            pass

        self._chunks_col = self._client.create_collection(
            name="folio_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        self._questions_col = self._client.create_collection(
            name="folio_questions",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Chroma collections reset successfully.")
        return {"folio_chunks": 0, "folio_questions": 0}

    def add_chunks(self, items: List[Dict[str, Any]]) -> None:
        """Add or update multiple text chunks in the folio_chunks collection with dimension safety."""
        if not items:
            return

        dim = len(items[0]["embedding"])
        current_meta = self._chunks_col.metadata or {}
        stored_dim = current_meta.get("embedding_dim")

        if stored_dim is not None:
            if int(stored_dim) != dim:
                raise AppError(
                    message="Vector store was created with a different embedding size (mock vs live). Call POST /api/v1/dev/vector-reset and re-run ingestion.",
                    code="embedding_dim_mismatch",
                    status_code=400,
                )
        else:
            # First insert: record dimension
            try:
                meta_update = {k: v for k, v in current_meta.items() if k != "hnsw:space"}
                meta_update["embedding_dim"] = dim
                self._chunks_col.modify(metadata=meta_update)
            except Exception as exc:
                logger.warning("Could not set embedding_dim in collection metadata: %s", exc)

        ids: List[str] = []
        embeddings: List[List[float]] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for item in items:
            chunk_id = int(item["chunk_id"])
            ids.append(str(chunk_id))
            embeddings.append(item["embedding"])
            documents.append(item["text"])

            meta: Dict[str, Any] = {
                "chunk_id": chunk_id,
                "course_id": int(item["course_id"]),
                "source_id": int(item["source_id"]),
            }
            if "topic_id" in item and item["topic_id"] is not None:
                meta["topic_id"] = int(item["topic_id"])
            metadatas.append(meta)

        try:
            self._chunks_col.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as exc:
            err_str = str(exc).lower()
            if "dimension" in err_str:
                raise AppError(
                    message="Vector store was created with a different embedding size (mock vs live). Call POST /api/v1/dev/vector-reset and re-run ingestion.",
                    code="embedding_dim_mismatch",
                    status_code=400,
                )
            raise

    def query_chunks(
        self,
        course_id: int,
        query_embedding: List[float],
        top_k: int = 5,
        topic_ids: Optional[List[int]] = None,
        chunk_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Query top-k most similar chunks for a course, filtered by course, topics, and/or chunk_ids."""
        total = self._chunks_col.count()
        if total == 0:
            return []

        # If chunk_ids filter requested but empty, no chunks match
        if chunk_ids is not None and len(chunk_ids) == 0:
            return []

        filter_conditions: List[Dict[str, Any]] = [{"course_id": course_id}]

        if chunk_ids is not None:
            if len(chunk_ids) == 1:
                filter_conditions.append({"chunk_id": chunk_ids[0]})
            else:
                filter_conditions.append({"chunk_id": {"$in": chunk_ids}})

        if topic_ids and len(topic_ids) > 0:
            if len(topic_ids) == 1:
                filter_conditions.append({"topic_id": topic_ids[0]})
            else:
                filter_conditions.append({"topic_id": {"$in": topic_ids}})

        if len(filter_conditions) == 1:
            where_filter: Dict[str, Any] = filter_conditions[0]
        else:
            where_filter = {"$and": filter_conditions}

        actual_k = min(top_k, total)
        try:
            results = self._chunks_col.query(
                query_embeddings=[query_embedding],
                n_results=actual_k,
                where=where_filter,
            )
        except Exception as exc:
            err_str = str(exc).lower()
            if "dimension" in err_str:
                raise AppError(
                    message="Vector store was created with a different embedding size (mock vs live). Call POST /api/v1/dev/vector-reset and re-run ingestion.",
                    code="embedding_dim_mismatch",
                    status_code=400,
                )
            raise

        output: List[Dict[str, Any]] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return output

        ids_list = results["ids"][0]
        distances_list = (
            results["distances"][0] if results.get("distances") else [0.0] * len(ids_list)
        )
        metas_list = (
            results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids_list)
        )
        docs_list = (
            results["documents"][0] if results.get("documents") else [""] * len(ids_list)
        )

        for id_str, dist, meta, doc in zip(
            ids_list, distances_list, metas_list, docs_list
        ):
            score = max(0.0, min(1.0, 1.0 - float(dist)))
            chunk_id = (
                int(meta["chunk_id"])
                if meta and "chunk_id" in meta
                else int(id_str.replace("chunk_", ""))
            )
            output.append(
                {
                    "chunk_id": chunk_id,
                    "score": round(score, 4),
                    "distance": round(float(dist), 4),
                    "text": doc,
                }
            )

        return output

    def delete_by_source(self, source_id: int) -> None:
        """Delete all chunks belonging to a specific source document."""
        self._chunks_col.delete(where={"source_id": source_id})

    def delete_by_course(self, course_id: int) -> None:
        """Delete all chunks belonging to a course."""
        self._chunks_col.delete(where={"course_id": course_id})

    def add_question(
        self,
        question_id: int,
        course_id: int,
        prompt: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add or update an assessment question vector with dimension safety."""
        item = {
            "question_id": question_id,
            "course_id": course_id,
            "prompt": prompt,
            "embedding": embedding,
        }
        if metadata:
            item.update(metadata)
        self.add_questions([item])

    def add_questions(self, items: List[Dict[str, Any]]) -> None:
        """Add or update multiple assessment questions with dimension safety."""
        if not items:
            return

        dim = len(items[0]["embedding"])
        current_meta = self._questions_col.metadata or {}
        stored_dim = current_meta.get("embedding_dim")

        if stored_dim is not None:
            if int(stored_dim) != dim:
                raise AppError(
                    message="Vector store was created with a different embedding size (mock vs live).",
                    code="embedding_dim_mismatch",
                    status_code=400,
                )
        else:
            try:
                meta_update = {k: v for k, v in current_meta.items() if k != "hnsw:space"}
                meta_update["embedding_dim"] = dim
                self._questions_col.modify(metadata=meta_update)
            except Exception as exc:
                logger.warning("Could not set embedding_dim in questions collection metadata: %s", exc)

        ids: List[str] = []
        embeddings: List[List[float]] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for item in items:
            q_id = int(item["question_id"])
            ids.append(f"q_{q_id}")
            embeddings.append(item["embedding"])
            documents.append(item.get("prompt", item.get("text", "")))

            meta: Dict[str, Any] = {
                "question_id": q_id,
                "course_id": int(item["course_id"]),
            }
            if "student_id" in item and item["student_id"] is not None:
                meta["student_id"] = int(item["student_id"])
            if "assessment_id" in item and item["assessment_id"] is not None:
                meta["assessment_id"] = int(item["assessment_id"])
            if "topic_id" in item and item["topic_id"] is not None:
                meta["topic_id"] = int(item["topic_id"])

            metadatas.append(meta)

        try:
            self._questions_col.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as exc:
            err_str = str(exc).lower()
            if "dimension" in err_str:
                raise AppError(
                    message="Vector store was created with a different embedding size (mock vs live).",
                    code="embedding_dim_mismatch",
                    status_code=400,
                )
            raise

    def query_similar_questions(
        self,
        course_id: int,
        embedding: List[float],
        top_k: int = 5,
        student_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query top-k most similar questions in a course, optionally filtered by student_id."""
        total = self._questions_col.count()
        if total == 0:
            return []

        actual_k = min(top_k, total)
        where_filter: Dict[str, Any]
        if student_id is not None:
            where_filter = {
                "$and": [
                    {"course_id": int(course_id)},
                    {"student_id": int(student_id)},
                ]
            }
        else:
            where_filter = {"course_id": int(course_id)}

        results = self._questions_col.query(
            query_embeddings=[embedding],
            n_results=actual_k,
            where=where_filter,
        )

        output: List[Dict[str, Any]] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return output

        ids_list = results["ids"][0]
        distances_list = (
            results["distances"][0] if results.get("distances") else [0.0] * len(ids_list)
        )
        metas_list = (
            results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids_list)
        )
        docs_list = (
            results["documents"][0] if results.get("documents") else [""] * len(ids_list)
        )

        for id_str, dist, meta, doc in zip(
            ids_list, distances_list, metas_list, docs_list
        ):
            score = max(0.0, min(1.0, 1.0 - float(dist)))
            question_id = (
                int(meta["question_id"])
                if meta and "question_id" in meta
                else int(id_str.replace("q_", ""))
            )
            output.append(
                {
                    "question_id": question_id,
                    "score": round(score, 4),
                    "distance": round(float(dist), 4),
                    "prompt": doc,
                    "student_id": meta.get("student_id") if meta else None,
                    "assessment_id": meta.get("assessment_id") if meta else None,
                    "topic_id": meta.get("topic_id") if meta else None,
                }
            )

        return output

    def delete_questions_by_assessment(self, assessment_id: int) -> None:
        """Delete all questions belonging to an assessment."""
        self._questions_col.delete(where={"assessment_id": int(assessment_id)})

    def delete_questions_by_course(self, course_id: int) -> None:
        """Delete all questions belonging to a course."""
        self._questions_col.delete(where={"course_id": course_id})


@lru_cache
def get_vector_store() -> VectorStore:
    """Dependency / singleton provider for VectorStore."""
    settings = get_settings()
    return VectorStore(settings)
