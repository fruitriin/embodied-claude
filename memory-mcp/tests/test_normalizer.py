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
        """ヴァ→バに変換される（カタカナのまま）。"""
        result = normalize_japanese("ヴァイオリン")
        assert result == "バイオリン"

    def test_unify_v_sounds_vi(self) -> None:
        """ヴィ→ビに変換される（カタカナのまま）。"""
        result = normalize_japanese("ヴィラ")
        assert result == "ビラ"

    def test_unify_v_sounds_vu(self) -> None:
        """ヴ単体→ブに変換される（カタカナのまま）。"""
        result = normalize_japanese("ヴ")
        assert result == "ブ"

    def test_unify_v_sounds_ve(self) -> None:
        """ヴェ→ベに変換される（カタカナのまま）。"""
        result = normalize_japanese("ヴェネチア")
        assert result == "ベネチア"

    def test_unify_v_sounds_vo(self) -> None:
        """ヴォ→ボに変換される（カタカナのまま）。"""
        result = normalize_japanese("ヴォイス")
        assert result == "ボイス"

    def test_unify_prolonged_sound_ascii_hyphen(self) -> None:
        """ASCIIハイフン→長音符ーに変換される。"""
        result = normalize_japanese("サ-バ")
        assert "ー" in result

    def test_unify_prolonged_sound_fullwidth_hyphen(self) -> None:
        """全角ハイフン→長音符ーに変換される。"""
        result = normalize_japanese("サ－バ")
        assert "ー" in result

    def test_katakana_unchanged(self) -> None:
        """カタカナはひらがなに変換されない（E5の意味理解に委ねる）。"""
        assert normalize_japanese("サーバー") == "サーバー"

    def test_server_hyphen_normalized(self) -> None:
        """サ-バのハイフンは長音符に変換される。"""
        assert normalize_japanese("サ-バ") == "サーバ"

    def test_server_variants_hyphen_matches(self) -> None:
        """サーバ と サ-バ は同じ正規化結果になる。"""
        assert normalize_japanese("サーバ") == normalize_japanese("サ-バ")

    def test_katakana_database_unchanged(self) -> None:
        """データベースはひらがなに変換されない。"""
        assert normalize_japanese("データベース") == "データベース"

    def test_lowercase_english(self) -> None:
        """英字大文字→小文字に統一される。"""
        assert normalize_japanese("SERVER") == "server"

    def test_mixed_jp_en(self) -> None:
        """日英混在テキストも正規化される。"""
        result = normalize_japanese("サーバーABCデータ")
        assert result == "サーバーabcデータ"

    def test_hiragana_unchanged(self) -> None:
        """ひらがなのテキストは変わらない。"""
        assert normalize_japanese("さーばー") == "さーばー"

    def test_empty_string(self) -> None:
        """空文字列はそのまま返される。"""
        assert normalize_japanese("") == ""
