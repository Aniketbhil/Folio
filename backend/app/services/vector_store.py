import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


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

    def add_chunks(self, items: List[Dict[str, Any]]) -> None:
        """Add or update multiple text chunks in the folio_chunks collection.

        Each item must contain:
        - chunk_id: int
        - course_id: int
        - source_id: int
        - text: str
        - embedding: list[float]
        Optional: topic_id, etc.
        """
        if not items:
            return

        ids: List[str] = []
        embeddings: List[List[float]] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for item in items:
            chunk_id = int(item["chunk_id"])
            ids.append(f"chunk_{chunk_id}")
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

        self._chunks_col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query_chunks(
        self,
        course_id: int,
        query_embedding: List[float],
        top_k: int = 5,
        topic_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Query top-k most similar chunks for a specific course, optionally filtered by topics."""
        total = self._chunks_col.count()
        if total == 0:
            return []

        if topic_ids and len(topic_ids) > 0:
            if len(topic_ids) == 1:
                where_filter: Dict[str, Any] = {
                    "$and": [
                        {"course_id": course_id},
                        {"topic_id": topic_ids[0]},
                    ]
                }
            else:
                where_filter = {
                    "$and": [
                        {"course_id": course_id},
                        {"topic_id": {"$in": topic_ids}},
                    ]
                }
        else:
            where_filter = {"course_id": course_id}

        actual_k = min(top_k, total)
        results = self._chunks_col.query(
            query_embeddings=[query_embedding],
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
        """Add or update an assessment question vector."""
        meta: Dict[str, Any] = {
            "question_id": int(question_id),
            "course_id": int(course_id),
        }
        if metadata:
            meta.update(metadata)

        self._questions_col.upsert(
            ids=[f"q_{question_id}"],
            embeddings=[embedding],
            documents=[prompt],
            metadatas=[meta],
        )

    def query_similar_questions(
        self,
        course_id: int,
        embedding: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Query top-k most similar questions in a course."""
        total = self._questions_col.count()
        if total == 0:
            return []

        actual_k = min(top_k, total)
        results = self._questions_col.query(
            query_embeddings=[embedding],
            n_results=actual_k,
            where={"course_id": course_id},
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
                }
            )

        return output

    def delete_questions_by_course(self, course_id: int) -> None:
        """Delete all questions belonging to a course."""
        self._questions_col.delete(where={"course_id": course_id})


@lru_cache
def get_vector_store() -> VectorStore:
    """Dependency / singleton provider for VectorStore."""
    settings = get_settings()
    return VectorStore(settings)
