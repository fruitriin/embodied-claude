"""日本語テキスト正規化モジュール。

pgroonga の NormalizerNFKC150 の安全なサブセットを Pure Python で実装する。
Docker・システム依存なし、標準ライブラリのみ使用。

対応する正規化：
- NFKC 正規化（全角英数→半角、半角カナ→全角カナ）
- unify_katakana_v_sounds（ヴァ→バ等）
- unify_hyphen_and_prolonged_sound_mark（ハイフン系→長音符ー）
- 英字大小統一

カタカナ→ひらがな変換は行わない。
multilingual-e5-base は自然な日本語テキスト（混在）で学習されているため、
カタカナ統一はむしろ意味表現の品質を下げる可能性がある。
送り仮名ゆれ（打ち合わせ↔打合せ）等は E5 の意味理解に委ねる。
"""

from __future__ import annotations

import re
import unicodedata

# ハイフン系文字を長音符ーに統一（unify_hyphen_and_prolonged_sound_mark 相当）
# 対象: ASCIIハイフン, 各種ダッシュ類, MINUS SIGN, 全角ハイフン等
_HYPHEN_RE = re.compile(r"[-\u2010\u2011\u2012\u2013\u2014\u2015\u207B\u208B\u2212\uFE63\uFF0D]")


def _unify_v_sounds(text: str) -> str:
    """ヴ行→バ行に変換（unify_katakana_v_sounds 相当）。

    ヴ（U+30F4）はNFKCでも変換されないため、個別に対応する。
    """
    return (
        text.replace("ヴァ", "バ")
        .replace("ヴィ", "ビ")
        .replace("ヴェ", "ベ")
        .replace("ヴォ", "ボ")
        .replace("ヴ", "ブ")
    )


def _unify_prolonged_sound(text: str) -> str:
    """ハイフン系文字をカタカナ長音符「ー」に統一。

    unify_hyphen_and_prolonged_sound_mark 相当。
    サーバ-・サ-バ等の混在を「サーバー」に正規化する。
    """
    return _HYPHEN_RE.sub("ー", text)


def normalize_japanese(text: str) -> str:
    """日本語テキストの表記ゆれを正規化する。

    以下の順で正規化を適用:
    1. NFKC 正規化（全角英数→半角、半角カナ→全角カナ、合成文字正規化）
    2. ヴ行→バ行（unify_katakana_v_sounds）
    3. ハイフン系→長音符ー（unify_hyphen_and_prolonged_sound_mark）
    4. 英字小文字化

    保存時・検索クエリ時の両方に同じ関数を適用することで、
    表記ゆれがあっても同じ正規化済みテキストとしてマッチングされる。

    Args:
        text: 正規化するテキスト

    Returns:
        正規化済みテキスト

    Examples:
        >>> normalize_japanese("サーバー")
        'サーバー'
        >>> normalize_japanese("サ-バ")
        'サーバ'
        >>> normalize_japanese("ヴァイオリン")
        'バイオリン'
        >>> normalize_japanese("Ａｂｃ")
        'abc'
    """
    # 1. NFKC: 全角英数→半角, 半角カナ→全角カナ
    text = unicodedata.normalize("NFKC", text)
    # 2. ヴ行→バ行
    text = _unify_v_sounds(text)
    # 3. ハイフン系→長音符ー
    text = _unify_prolonged_sound(text)
    # 4. 英字小文字化
    text = text.lower()
    return text
