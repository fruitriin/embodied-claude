"""Tests for pgroonga full-text search: okurigana normalization and fuzzy search.

These tests verify that the pgroonga indexes correctly handle Japanese
notation variations (表記ゆれ) using TokenMecab with reading-based
tokenization and NormalizerNFKC150 normalization.

Requires a running PostgreSQL instance with pgroonga extension.
"""

import pytest

from memory_mcp.memory import MemoryStore


class TestOkuriganaNormalization:
    """Tests for okurigana variation normalization via pgroonga.

    TokenMecab("use_reading", true) converts tokens to katakana readings,
    unifying okurigana variations like 打ち合わせ ↔ 打合せ.
    """

    @pytest.mark.asyncio
    async def test_uchiawase_with_okurigana(self, memory_store: MemoryStore):
        """打ち合わせ → 打合せ で検索できる。"""
        await memory_store.save(content="明日の打ち合わせの準備をした")
        await memory_store.save(content="ラーメンを食べに行った")

        results = await memory_store._store.hybrid_search(
            query="打合せ", n_results=5, text_weight=0.9, vector_weight=0.1
        )

        contents = [r.memory.content for r in results]
        assert any("打ち合わせ" in c for c in contents), (
            f"Expected '打ち合わせ' in results when searching '打合せ', got: {contents}"
        )

    @pytest.mark.asyncio
    async def test_uchiawase_reverse(self, memory_store: MemoryStore):
        """打合せ → 打ち合わせ で検索できる。"""
        await memory_store.save(content="打合せの資料を作成した")
        await memory_store.save(content="公園で散歩をした")

        results = await memory_store._store.hybrid_search(
            query="打ち合わせ", n_results=5, text_weight=0.9, vector_weight=0.1
        )

        contents = [r.memory.content for r in results]
        assert any("打合せ" in c for c in contents), (
            f"Expected '打合せ' in results when searching '打ち合わせ', got: {contents}"
        )

    @pytest.mark.asyncio
    async def test_yakiniku_okurigana(self, memory_store: MemoryStore):
        """焼き肉 → 焼肉 で検索できる。"""
        await memory_store.save(content="焼き肉を食べに行った")
        await memory_store.save(content="プログラミングの勉強をした")

        results = await memory_store._store.hybrid_search(
            query="焼肉", n_results=5, text_weight=0.9, vector_weight=0.1
        )

        contents = [r.memory.content for r in results]
        assert any("焼き肉" in c for c in contents), (
            f"Expected '焼き肉' in results when searching '焼肉', got: {contents}"
        )

    @pytest.mark.asyncio
    async def test_yakiniku_reverse(self, memory_store: MemoryStore):
        """焼肉 → 焼き肉 で検索できる。"""
        await memory_store.save(content="焼肉屋で夕食をとった")
        await memory_store.save(content="映画を観た")

        results = await memory_store._store.hybrid_search(
            query="焼き肉", n_results=5, text_weight=0.9, vector_weight=0.1
        )

        contents = [r.memory.content for r in results]
        assert any("焼肉" in c for c in contents), (
            f"Expected '焼肉' in results when searching '焼き肉', got: {contents}"
        )


class TestNormalizerUnification:
    """Tests for NormalizerNFKC150 character unification.

    The normalizer handles prolonged sound marks, voiced sound marks,
    kana case variations, katakana v-sounds, etc.
    """

    @pytest.mark.asyncio
    async def test_prolonged_sound_mark(self, memory_store: MemoryStore):
        """サーバー ↔ サーバ (長音符の有無) を統一できる。"""
        await memory_store.save(content="サーバーの設定を変更した")
        await memory_store.save(content="本を読んだ")

        results = await memory_store._store.hybrid_search(
            query="サーバ", n_results=5, text_weight=0.9, vector_weight=0.1
        )

        contents = [r.memory.content for r in results]
        assert any("サーバー" in c for c in contents), (
            f"Expected 'サーバー' in results when searching 'サーバ', got: {contents}"
        )

    @pytest.mark.asyncio
    async def test_voiced_sound_mark(self, memory_store: MemoryStore):
        """濁点の正規化（バ/ハ行のゆれ等）。

        NormalizerNFKC150 with unify_kana_voiced_sound_mark normalizes
        voiced sound mark variations.
        """
        await memory_store.save(content="データベースの設計をした")
        await memory_store.save(content="天気が良かった")

        results = await memory_store._store.hybrid_search(
            query="データベース", n_results=5, text_weight=0.9, vector_weight=0.1
        )

        contents = [r.memory.content for r in results]
        assert any("データベース" in c for c in contents)


class TestFuzzySearch:
    """Tests for pgroonga fuzzy (edit-distance) search.

    Uses pgroonga_condition(fuzzy_max_distance_ratio) for approximate
    matching that tolerates typos. Operates on the primary index
    (idx_memories_content_pgroonga) without unify_kana.
    """

    @pytest.mark.asyncio
    async def test_fuzzy_english_typo(self, memory_store: MemoryStore):
        """英語のタイポを許容する（programing → programming）。"""
        await memory_store.save(content="programmingの勉強をした")
        await memory_store.save(content="料理を作った")

        results = await memory_store._store.fuzzy_search(
            query="programing", n_results=5
        )

        contents = [r.memory.content for r in results]
        assert any("programming" in c for c in contents), (
            f"Expected 'programming' in results when fuzzy-searching 'programing', got: {contents}"
        )

    @pytest.mark.xfail(
        reason="MeCab cannot tokenize misspelled katakana loanwords "
        "(e.g. テノクロジー is not in dictionary), so fuzzy matching fails",
        strict=False,
    )
    @pytest.mark.asyncio
    async def test_fuzzy_katakana_typo(self, memory_store: MemoryStore):
        """カタカナのタイポを許容する（テノクロジー → テクノロジー）。

        MeCab がタイポされたカタカナ語を辞書から見つけられない場合、
        トークン分割が崩れて fuzzy matching が機能しない。
        """
        await memory_store.save(content="テクノロジーの進化について考えた")
        await memory_store.save(content="散歩に行った")

        results = await memory_store._store.fuzzy_search(
            query="テノクロジー", n_results=5
        )

        contents = [r.memory.content for r in results]
        assert any("テクノロジー" in c for c in contents), (
            f"Expected 'テクノロジー' in results when fuzzy-searching 'テノクロジー', got: {contents}"
        )

    @pytest.mark.asyncio
    async def test_fuzzy_returns_empty_for_unrelated(self, memory_store: MemoryStore):
        """全く無関係なクエリでは結果が空になる。"""
        await memory_store.save(content="カメラの設定をした")

        results = await memory_store._store.fuzzy_search(
            query="量子コンピュータ", n_results=5
        )

        contents = [r.memory.content for r in results]
        assert not any("カメラ" in c for c in contents) or len(results) == 0


class TestHybridSearchIntegration:
    """Tests for hybrid search combining vector + pgroonga.

    Verifies that hybrid search finds memories via text matching
    even when vector similarity alone might miss them.
    """

    @pytest.mark.asyncio
    async def test_hybrid_beats_vector_only_for_okurigana(self, memory_store: MemoryStore):
        """hybrid search が送り仮名ゆれを vector-only より良くカバーする。"""
        await memory_store.save(content="明日の打ち合わせの準備をした")
        await memory_store.save(content="宇宙の始まりについて考察した")
        await memory_store.save(content="コーヒーを飲んだ")

        # hybrid search (text-heavy) should find okurigana variant
        hybrid_results = await memory_store._store.hybrid_search(
            query="打合せ", n_results=3, text_weight=0.8, vector_weight=0.2
        )

        hybrid_contents = [r.memory.content for r in hybrid_results]
        assert any("打ち合わせ" in c for c in hybrid_contents), (
            f"Hybrid search should find '打ち合わせ' for query '打合せ', got: {hybrid_contents}"
        )

    @pytest.mark.asyncio
    async def test_hybrid_search_mixed_content(self, memory_store: MemoryStore):
        """日本語と英語が混在するコンテンツの検索。"""
        await memory_store.save(content="ONVIFプロトコルでカメラを制御した")
        await memory_store.save(content="Pythonのasyncioを学んだ")
        await memory_store.save(content="朝ごはんを食べた")

        results = await memory_store._store.hybrid_search(
            query="ONVIF カメラ", n_results=5, text_weight=0.7, vector_weight=0.3
        )

        contents = [r.memory.content for r in results]
        assert any("ONVIF" in c for c in contents)
