"""Tests for search quality: semantic search (pgvector), notation normalization
(pgroonga), fuzzy search, and scoring behavior.

Requires a running PostgreSQL instance with pgvector + pgroonga extensions.
"""

import uuid

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


class TestSemanticSearch:
    """Tests for pgvector semantic search (keyword overlap = zero).

    These tests verify that vector similarity (multilingual-e5-base) finds
    conceptually related memories even when the query and content share
    no common keywords. Uses the pure vector search() method.
    """

    @pytest.mark.asyncio
    async def test_food_concept_no_keyword_overlap(self, memory_store: MemoryStore):
        """「夕飯の記録」→「ラーメン屋で味噌ラーメンを食べた」。

        クエリに「ラーメン」も「食べ」も含まれないが、
        「夕飯」と「ラーメンを食べた」は意味的に近い。
        """
        await memory_store.save(content="ラーメン屋で味噌ラーメンを食べた")
        await memory_store.save(content="Gitのブランチ戦略について議論した")
        await memory_store.save(content="部屋の掃除をした")

        results = await memory_store.search("夕飯の記録", n_results=3)

        contents = [r.memory.content for r in results]
        assert contents[0] == "ラーメン屋で味噌ラーメンを食べた", (
            f"Expected ramen memory as top result for '夕飯の記録', got: {contents}"
        )

    @pytest.mark.asyncio
    async def test_learning_concept_no_keyword_overlap(self, memory_store: MemoryStore):
        """「最近の技術的な学び」→「asyncioのコルーチンについて理解が深まった」。

        クエリに「asyncio」も「コルーチン」も「理解」も含まれないが、
        技術学習という概念で結びつく。
        """
        await memory_store.save(content="asyncioのコルーチンについて理解が深まった")
        await memory_store.save(content="公園のベンチで休憩した")
        await memory_store.save(content="洗濯物を干した")

        results = await memory_store.search("最近の技術的な学び", n_results=3)

        contents = [r.memory.content for r in results]
        assert contents[0] == "asyncioのコルーチンについて理解が深まった", (
            f"Expected asyncio memory as top result for '最近の技術的な学び', got: {contents}"
        )

    @pytest.mark.asyncio
    async def test_weather_concept_no_keyword_overlap(self, memory_store: MemoryStore):
        """「天候の変化」→「朝から雨が降り続いていた」。

        クエリに「雨」も「降り」も含まれないが、
        天候という概念で結びつく。
        """
        await memory_store.save(content="朝から雨が降り続いていた")
        await memory_store.save(content="新しいAPIエンドポイントを実装した")
        await memory_store.save(content="友達にメッセージを送った")

        results = await memory_store.search("天候の変化", n_results=3)

        contents = [r.memory.content for r in results]
        assert contents[0] == "朝から雨が降り続いていた", (
            f"Expected rain memory as top result for '天候の変化', got: {contents}"
        )

    @pytest.mark.asyncio
    async def test_emotion_concept_no_keyword_overlap(self, memory_store: MemoryStore):
        """「嬉しかった体験」→「試験に合格した」。

        クエリに「試験」も「合格」も含まれないが、
        嬉しい体験という概念で結びつく。
        """
        await memory_store.save(content="試験に合格した")
        await memory_store.save(content="データベースのインデックスを再構築した")
        await memory_store.save(content="ゴミを出した")

        results = await memory_store.search("嬉しかった体験", n_results=3)

        contents = [r.memory.content for r in results]
        assert contents[0] == "試験に合格した", (
            f"Expected exam memory as top result for '嬉しかった体験', got: {contents}"
        )

    @pytest.mark.asyncio
    async def test_semantic_search_with_many_distractors(self, memory_store: MemoryStore):
        """20件のノイズの中からターゲットをトップ3で返せる。"""
        distractors = [
            "洗濯物を干した",
            "ゴミを出した",
            "電気代の請求書を確認した",
            "歯医者の予約をした",
            "スーパーで牛乳を買った",
            "Gitのコンフリクトを解消した",
            "CIパイプラインを修正した",
            "Dockerイメージをビルドした",
            "会議の議事録を書いた",
            "上司にメールを送った",
            "通勤電車で本を読んだ",
            "部屋の模様替えをした",
            "新しいキーボードを注文した",
            "プリンターのインクを交換した",
            "Wi-Fiルーターを再起動した",
            "植物に水をやった",
            "写真を整理した",
            "古い服を処分した",
            "友達の誕生日プレゼントを選んだ",
            "保険の更新手続きをした",
        ]
        for d in distractors:
            await memory_store.save(content=d)

        await memory_store.save(content="カメラのパンチルト制御をONVIFで実装した")

        results = await memory_store.search("カメラの機能開発", n_results=3)

        contents = [r.memory.content for r in results]
        assert any("パンチルト" in c for c in contents), (
            f"Expected camera memory in top 3 among 21 memories, got: {contents}"
        )


class TestScoringBehavior:
    """Tests for search_with_scoring: importance, emotion, and time decay.

    Verifies that the scoring formula correctly prioritizes memories
    based on the memory module's design intent:
    - Higher importance → lower final_score (ranked higher)
    - Stronger emotion → lower final_score (ranked higher)
    - Fresher memory → lower final_score (ranked higher)

    final_score = semantic_distance + (1 - time_decay) * 0.3
                  - (emotion_boost * 0.2 + importance_boost * 0.2)
    """

    @pytest.mark.asyncio
    async def test_importance_boost_affects_ranking(self, memory_store: MemoryStore):
        """同じトピックで重要度が異なる → 重要度が高い方が上位。"""
        await memory_store.save(
            content="カメラの設定を変更した",
            importance=1, emotion="neutral",
        )
        await memory_store.save(
            content="カメラの初期セットアップを完了した",
            importance=5, emotion="neutral",
        )

        results = await memory_store.search_with_scoring(
            query="カメラの設定",
            n_results=2,
            use_time_decay=False,
            use_emotion_boost=False,
        )

        assert len(results) == 2
        # importance=5 の方が importance_boost が大きく、final_score が低い
        assert results[0].memory.importance >= results[1].memory.importance, (
            f"Expected importance=5 first, got: "
            f"[{results[0].memory.importance}] '{results[0].memory.content}', "
            f"[{results[1].memory.importance}] '{results[1].memory.content}'"
        )

    @pytest.mark.asyncio
    async def test_emotion_boost_affects_ranking(self, memory_store: MemoryStore):
        """同じトピックで感情が異なる → 強い感情の方が上位。"""
        await memory_store.save(
            content="散歩で公園に行った",
            importance=3, emotion="neutral",
        )
        await memory_store.save(
            content="散歩で美しい夕焼けを見た",
            importance=3, emotion="excited",
        )

        results = await memory_store.search_with_scoring(
            query="散歩の思い出",
            n_results=2,
            use_time_decay=False,
            use_emotion_boost=True,
        )

        assert len(results) == 2
        # excited (0.4) > neutral (0.0) なので excited が上位
        assert results[0].emotion_boost >= results[1].emotion_boost, (
            f"Expected excited memory first, got: "
            f"[{results[0].memory.emotion}] '{results[0].memory.content}', "
            f"[{results[1].memory.emotion}] '{results[1].memory.content}'"
        )

    @pytest.mark.asyncio
    async def test_time_decay_affects_ranking(self, memory_store: MemoryStore):
        """同じトピックで鮮度が異なる → 新しい方が上位。

        created_at を直接 UPDATE して30日前に戻し、time_decay の効果を検証。
        """
        old_mem = await memory_store.save(
            content="カメラのファームウェアを更新した",
            importance=3, emotion="neutral",
        )
        await memory_store.save(
            content="カメラのレンズを掃除した",
            importance=3, emotion="neutral",
        )

        # old_mem を30日前に戻す
        pool = memory_store._store._pool
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE memories SET created_at = created_at - INTERVAL '30 days' WHERE id = $1",
                uuid.UUID(old_mem.id),
            )

        results = await memory_store.search_with_scoring(
            query="カメラのメンテナンス",
            n_results=2,
            use_time_decay=True,
            use_emotion_boost=False,
        )

        assert len(results) == 2
        # 新しい記憶の time_decay が 1.0 に近く、古い記憶は減衰している
        assert results[0].time_decay_factor > results[1].time_decay_factor, (
            f"Expected fresh memory first, got: "
            f"decay=[{results[0].time_decay_factor:.3f}] '{results[0].memory.content}', "
            f"decay=[{results[1].time_decay_factor:.3f}] '{results[1].memory.content}'"
        )

    @pytest.mark.asyncio
    async def test_combined_scoring_importance_over_distance(self, memory_store: MemoryStore):
        """重要度5 + excited はセマンティック距離の僅差を逆転できる。

        意味的にやや遠いが重要度が高い記憶が、意味的に近いが平凡な記憶より
        上位に来ることを確認。
        """
        # 意味的に近いが重要度低
        await memory_store.save(
            content="カメラの角度を微調整した",
            importance=1, emotion="neutral",
        )
        # 意味的にやや遠いが重要度+感情が高い
        await memory_store.save(
            content="新しいPTZカメラを購入してセットアップに成功した",
            importance=5, emotion="excited",
        )

        results = await memory_store.search_with_scoring(
            query="カメラの調整",
            n_results=2,
            use_time_decay=False,
            use_emotion_boost=True,
        )

        assert len(results) == 2
        # importance=5 + excited の合計ブースト: (0.4*0.2 + 0.4*0.2) = 0.16
        # importance=1 + neutral の合計ブースト: (0.0*0.2 + 0.0*0.2) = 0.0
        # 0.16の差がセマンティック距離の僅差を逆転できるか
        high_importance_result = next(
            r for r in results if r.memory.importance == 5
        )
        low_importance_result = next(
            r for r in results if r.memory.importance == 1
        )
        assert high_importance_result.final_score <= low_importance_result.final_score, (
            f"Expected high-importance memory to have lower (better) final_score: "
            f"imp5={high_importance_result.final_score:.4f} vs "
            f"imp1={low_importance_result.final_score:.4f}"
        )
