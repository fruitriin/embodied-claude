"""Memory operations with ChromaDB."""

import asyncio
import uuid
from datetime import datetime
from typing import Any

import chromadb

from .config import MemoryConfig
from .types import Memory, MemorySearchResult, MemoryStats


class MemoryStore:
    """ChromaDB-backed memory storage."""

    def __init__(self, config: MemoryConfig):
        self._config = config
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize ChromaDB connection."""
        async with self._lock:
            if self._client is None:
                self._client = await asyncio.to_thread(
                    chromadb.PersistentClient,
                    path=self._config.db_path,
                )
                self._collection = await asyncio.to_thread(
                    self._client.get_or_create_collection,
                    name=self._config.collection_name,
                    metadata={"description": "Claude's long-term memories"},
                )

    async def disconnect(self) -> None:
        """Close ChromaDB connection."""
        async with self._lock:
            self._client = None
            self._collection = None

    def _ensure_connected(self) -> chromadb.Collection:
        """Ensure connected and return collection."""
        if self._collection is None:
            raise RuntimeError("MemoryStore not connected. Call connect() first.")
        return self._collection

    async def save(
        self,
        content: str,
        emotion: str = "neutral",
        importance: int = 3,
        category: str = "daily",
    ) -> Memory:
        """Save a new memory."""
        collection = self._ensure_connected()

        memory_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        importance = max(1, min(5, importance))  # Clamp to 1-5

        memory = Memory(
            id=memory_id,
            content=content,
            timestamp=timestamp,
            emotion=emotion,
            importance=importance,
            category=category,
        )

        await asyncio.to_thread(
            collection.add,
            ids=[memory_id],
            documents=[content],
            metadatas=[memory.to_metadata()],
        )

        return memory

    async def search(
        self,
        query: str,
        n_results: int = 5,
        emotion_filter: str | None = None,
        category_filter: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[MemorySearchResult]:
        """Search memories by semantic similarity."""
        collection = self._ensure_connected()

        # Build where filter
        where_conditions: list[dict[str, Any]] = []

        if emotion_filter:
            where_conditions.append({"emotion": {"$eq": emotion_filter}})
        if category_filter:
            where_conditions.append({"category": {"$eq": category_filter}})
        if date_from:
            where_conditions.append({"timestamp": {"$gte": date_from}})
        if date_to:
            where_conditions.append({"timestamp": {"$lte": date_to}})

        where: dict[str, Any] | None = None
        if len(where_conditions) == 1:
            where = where_conditions[0]
        elif len(where_conditions) > 1:
            where = {"$and": where_conditions}

        results = await asyncio.to_thread(
            collection.query,
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        search_results: list[MemorySearchResult] = []

        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for i, memory_id in enumerate(ids):
                memory = Memory(
                    id=memory_id,
                    content=documents[i] if i < len(documents) else "",
                    timestamp=metadatas[i].get("timestamp", "") if i < len(metadatas) else "",
                    emotion=metadatas[i].get("emotion", "neutral") if i < len(metadatas) else "neutral",
                    importance=metadatas[i].get("importance", 3) if i < len(metadatas) else 3,
                    category=metadatas[i].get("category", "daily") if i < len(metadatas) else "daily",
                )
                distance = distances[i] if i < len(distances) else 0.0
                search_results.append(MemorySearchResult(memory=memory, distance=distance))

        return search_results

    async def recall(
        self,
        context: str,
        n_results: int = 3,
    ) -> list[MemorySearchResult]:
        """Recall relevant memories based on current context."""
        return await self.search(query=context, n_results=n_results)

    async def list_recent(
        self,
        limit: int = 10,
        category_filter: str | None = None,
    ) -> list[Memory]:
        """List recent memories sorted by timestamp."""
        collection = self._ensure_connected()

        where: dict[str, Any] | None = None
        if category_filter:
            where = {"category": {"$eq": category_filter}}

        results = await asyncio.to_thread(
            collection.get,
            where=where,
        )

        memories: list[Memory] = []

        if results and results.get("ids"):
            ids = results["ids"]
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])

            for i, memory_id in enumerate(ids):
                memory = Memory(
                    id=memory_id,
                    content=documents[i] if i < len(documents) else "",
                    timestamp=metadatas[i].get("timestamp", "") if i < len(metadatas) else "",
                    emotion=metadatas[i].get("emotion", "neutral") if i < len(metadatas) else "neutral",
                    importance=metadatas[i].get("importance", 3) if i < len(metadatas) else 3,
                    category=metadatas[i].get("category", "daily") if i < len(metadatas) else "daily",
                )
                memories.append(memory)

        # Sort by timestamp (newest first) and limit
        memories.sort(key=lambda m: m.timestamp, reverse=True)
        return memories[:limit]

    async def get_stats(self) -> MemoryStats:
        """Get statistics about stored memories."""
        collection = self._ensure_connected()

        results = await asyncio.to_thread(collection.get)

        total_count = len(results.get("ids", []))
        by_category: dict[str, int] = {}
        by_emotion: dict[str, int] = {}
        timestamps: list[str] = []

        for metadata in results.get("metadatas", []):
            category = metadata.get("category", "daily")
            emotion = metadata.get("emotion", "neutral")
            timestamp = metadata.get("timestamp", "")

            by_category[category] = by_category.get(category, 0) + 1
            by_emotion[emotion] = by_emotion.get(emotion, 0) + 1

            if timestamp:
                timestamps.append(timestamp)

        timestamps.sort()

        return MemoryStats(
            total_count=total_count,
            by_category=by_category,
            by_emotion=by_emotion,
            oldest_timestamp=timestamps[0] if timestamps else None,
            newest_timestamp=timestamps[-1] if timestamps else None,
        )
