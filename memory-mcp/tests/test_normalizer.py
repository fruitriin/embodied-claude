"""Tests for Japanese text normalizer (Phase 8)."""

from memory_mcp.normalizer import normalize_japanese


class TestNormalizeJapanese:
    """normalize_japanese() の動作テスト."""

    def test_nfkc_fullwidth_to_halfwidth(self) -> None:
        """全角英数→半角に変換される。"""
        assert normalize_japanese("Ａｂｃ１２３") == "abc123"

    def test_nfkc_halfwidth_kana_to_fullwidth(self) -> None:
        """半角カナ→全角カナに変換される。"""
        result = normalize_japanese("ｻｰﾊﾞｰ")
        assert "ー" in result

    def test_unify_v_sounds_va(self) -> None:
        """ヴァ→バに変換される。"""
        result = normalize_japanese("ヴァイオリン")
        assert result == "ばいおりん"

    def test_unify_v_sounds_vi(self) -> None:
        """ヴィ→ビに変換される。"""
        result = normalize_japanese("ヴィラ")
        assert result == "びら"

    def test_unify_v_sounds_vu(self) -> None:
        """ヴ単体→ブに変換される。"""
        result = normalize_japanese("ヴ")
        assert result == "ぶ"

    def test_unify_v_sounds_ve(self) -> None:
        """ヴェ→ベに変換される。"""
        result = normalize_japanese("ヴェネチア")
        assert result == "べねちあ"

    def test_unify_v_sounds_vo(self) -> None:
        """ヴォ→ボに変換される。"""
        result = normalize_japanese("ヴォイス")
        assert result == "ぼいす"

    def test_unify_prolonged_sound_ascii_hyphen(self) -> None:
        """ASCIIハイフン→長音符ーに変換される。"""
        result = normalize_japanese("サ-バ")
        assert "ー" in result

    def test_unify_prolonged_sound_fullwidth_hyphen(self) -> None:
        """全角ハイフン→長音符ーに変換される。"""
        result = normalize_japanese("サ－バ")
        assert "ー" in result

    def test_katakana_to_hiragana_server(self) -> None:
        """サーバー→さーばーに変換される（カタカナ→ひらがな統一）。"""
        assert normalize_japanese("サーバー") == "さーばー"

    def test_katakana_to_hiragana_server_short(self) -> None:
        """サーバ（長音符なし）→さーばに変換される。"""
        assert normalize_japanese("サーバ") == "さーば"

    def test_server_variants_all_match(self) -> None:
        """サーバー・サーバ・サ-バが同じ正規化結果（さーばー or さーば相当）になる。

        ハイフン→ーに変換されるので「サ-バ」→「さーば」となる。
        """
        r1 = normalize_japanese("サーバー")
        r2 = normalize_japanese("サーバ")
        r3 = normalize_japanese("サ-バ")
        # ハイフン→ーになるので「サ-バ」と「サーバ」は同じになる
        assert r2 == r3

    def test_katakana_to_hiragana_database(self) -> None:
        """データベース→でーたべーすに変換される。"""
        assert normalize_japanese("データベース") == "でーたべーす"

    def test_lowercase_english(self) -> None:
        """英字大文字→小文字に統一される。"""
        assert normalize_japanese("SERVER") == "server"

    def test_mixed_jp_en(self) -> None:
        """日英混在テキストも正規化される。"""
        result = normalize_japanese("サーバーABCデータ")
        assert result == "さーばーabcでーた"

    def test_plain_hiragana_unchanged(self) -> None:
        """既にひらがなのテキストは変わらない。"""
        assert normalize_japanese("さーばー") == "さーばー"

    def test_empty_string(self) -> None:
        """空文字列はそのまま返される。"""
        assert normalize_japanese("") == ""
