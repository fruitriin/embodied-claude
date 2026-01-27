"""Tests for memory operations."""

import pytest

from memory_mcp.memory import MemoryStore


class TestMemorySave:
    """Tests for save_memory."""

    @pytest.mark.asyncio
    async def test_save_basic(self, memory_store: MemoryStore):
        """Test basic memory save."""
        memory = await memory_store.save(
            content="幼馴染と初めて会った日",
            emotion="happy",
            importance=5,
            category="memory",
        )

        assert memory.content == "幼馴染と初めて会った日"
        assert memory.emotion == "happy"
        assert memory.importance == 5
        assert memory.category == "memory"
        assert memory.id is not None
        assert memory.timestamp is not None

    @pytest.mark.asyncio
    async def test_save_with_defaults(self, memory_store: MemoryStore):
        """Test save with default values."""
        memory = await memory_store.save(content="Something happened")

        assert memory.emotion == "neutral"
        assert memory.importance == 3
        assert memory.category == "daily"

    @pytest.mark.asyncio
    async def test_importance_clamping(self, memory_store: MemoryStore):
        """Test importance is clamped to 1-5."""
        memory_low = await memory_store.save(content="Test low", importance=0)
        memory_high = await memory_store.save(content="Test high", importance=10)

        assert memory_low.importance == 1
        assert memory_high.importance == 5


class TestMemorySearch:
    """Tests for search_memories."""

    @pytest.mark.asyncio
    async def test_search_basic(self, memory_store: MemoryStore):
        """Test basic semantic search."""
        await memory_store.save(content="カメラで部屋を見た", category="observation")
        await memory_store.save(content="コードを書いた", category="technical")
        await memory_store.save(content="幼馴染と話した", category="memory")

        results = await memory_store.search("幼馴染との会話")

        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_with_category_filter(self, memory_store: MemoryStore):
        """Test search with category filter."""
        await memory_store.save(content="技術的な学び1", category="technical")
        await memory_store.save(content="日常の出来事", category="daily")
        await memory_store.save(content="技術的な学び2", category="technical")

        results = await memory_store.search("学び", category_filter="technical")

        assert len(results) > 0
        for result in results:
            assert result.memory.category == "technical"

    @pytest.mark.asyncio
    async def test_search_empty_results(self, memory_store: MemoryStore):
        """Test search with no matching results."""
        await memory_store.save(content="Something completely different")

        results = await memory_store.search(
            "非常に特殊なクエリ",
            category_filter="philosophical",
        )

        # May or may not find results depending on semantic similarity
        assert isinstance(results, list)


class TestMemoryRecall:
    """Tests for recall."""

    @pytest.mark.asyncio
    async def test_recall_context(self, memory_store: MemoryStore):
        """Test context-based recall."""
        await memory_store.save(content="Wi-Fiカメラを設置した")
        await memory_store.save(content="パン・チルト機能を実装した")
        await memory_store.save(content="美味しいラーメンを食べた")

        results = await memory_store.recall(context="カメラの機能について")

        assert len(results) > 0


class TestMemoryListRecent:
    """Tests for list_recent_memories."""

    @pytest.mark.asyncio
    async def test_list_recent_order(self, memory_store: MemoryStore):
        """Test that recent memories are returned in order."""
        await memory_store.save(content="Memory 1")
        await memory_store.save(content="Memory 2")
        await memory_store.save(content="Memory 3")

        memories = await memory_store.list_recent(limit=3)

        assert len(memories) == 3
        # Should be newest first
        assert memories[0].content == "Memory 3"
        assert memories[2].content == "Memory 1"

    @pytest.mark.asyncio
    async def test_list_recent_with_limit(self, memory_store: MemoryStore):
        """Test limit parameter."""
        for i in range(10):
            await memory_store.save(content=f"Memory {i}")

        memories = await memory_store.list_recent(limit=5)

        assert len(memories) == 5

    @pytest.mark.asyncio
    async def test_list_recent_with_category_filter(self, memory_store: MemoryStore):
        """Test category filter."""
        await memory_store.save(content="Tech 1", category="technical")
        await memory_store.save(content="Daily 1", category="daily")
        await memory_store.save(content="Tech 2", category="technical")

        memories = await memory_store.list_recent(category_filter="technical")

        assert len(memories) == 2
        for m in memories:
            assert m.category == "technical"


class TestMemoryStats:
    """Tests for get_memory_stats."""

    @pytest.mark.asyncio
    async def test_stats_counts(self, memory_store: MemoryStore):
        """Test statistics counts."""
        await memory_store.save(content="Happy memory", emotion="happy", category="daily")
        await memory_store.save(content="Sad memory", emotion="sad", category="feeling")
        await memory_store.save(content="Another happy", emotion="happy", category="daily")

        stats = await memory_store.get_stats()

        assert stats.total_count == 3
        assert stats.by_emotion.get("happy") == 2
        assert stats.by_emotion.get("sad") == 1
        assert stats.by_category.get("daily") == 2
        assert stats.by_category.get("feeling") == 1

    @pytest.mark.asyncio
    async def test_stats_empty(self, memory_store: MemoryStore):
        """Test stats with no memories."""
        stats = await memory_store.get_stats()

        assert stats.total_count == 0
        assert stats.oldest_timestamp is None
        assert stats.newest_timestamp is None
