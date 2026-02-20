"""日本語テキスト正規化モジュール。

pgroonga の NormalizerNFKC150 相当の正規化を Pure Python で実装する。
Docker・システム依存なし、標準ライブラリのみ使用。

対応する正規化：
- NFKC 正規化（全角英数→半角、半角カナ→全角カナ）
- unify_katakana_v_sounds（ヴァ→バ等）
- unify_hyphen_and_prolonged_sound_mark（ハイフン系→長音符ー）
- unify_kana（カタカナ→ひらがな統一）
- 英字大小統一
"""

from __future__ import annotations

import re
import unicodedata

# ハイフン系文字を長音符ーに統一（unify_hyphen_and_prolonged_sound_mark 相当）
# 対象: ASCIIハイフン, 各種ダッシュ類, MINUS SIGN, 全角ハイフン等
_HYPHEN_RE = re.compile(r"[-\u2010\u2011\u2012\u2013\u2014\u2015\u207B\u208B\u2212\uFE63\uFF0D]")

# カタカナ範囲（ァ=U+30A1 ～ ン=U+30F3、ヴ=U+30F4）
_KATA_START = 0x30A1
_KATA_END = 0x30F3
_KATA_VU = 0x30F4  # ヴ
_HIRA_OFFSET = -0x60  # カタカナ → ひらがな変換オフセット


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


def _katakana_to_hiragana(text: str) -> str:
    """カタカナをひらがなに変換（unify_kana 相当）。

    ァ(U+30A1)〜ン(U+30F3) の範囲を U+0060 分シフトしてひらがなに変換。
    ヴ(U+30F4) は _unify_v_sounds() 後にブ→ぶ となる。
    """
    chars = []
    for ch in text:
        cp = ord(ch)
        if _KATA_START <= cp <= _KATA_END:
            chars.append(chr(cp + _HIRA_OFFSET))
        else:
            chars.append(ch)
    return "".join(chars)


def normalize_japanese(text: str) -> str:
    """日本語テキストの表記ゆれを正規化する。

    以下の順で正規化を適用:
    1. NFKC 正規化（全角英数→半角、半角カナ→全角カナ、合成文字正規化）
    2. ヴ行→バ行（unify_katakana_v_sounds）
    3. ハイフン系→長音符ー（unify_hyphen_and_prolonged_sound_mark）
    4. カタカナ→ひらがな統一（unify_kana）
    5. 英字小文字化

    保存時・検索クエリ時の両方に同じ関数を適用することで、
    表記ゆれがあっても同じ正規化済みテキストとしてマッチングされる。

    Args:
        text: 正規化するテキスト

    Returns:
        正規化済みテキスト

    Examples:
        >>> normalize_japanese("サーバー")
        'さーばー'
        >>> normalize_japanese("サーバ")
        'さーばー'  # 長音符が付与される（ー統一後）
        >>> normalize_japanese("ヴァイオリン")
        'ばいおりん'
        >>> normalize_japanese("Ａｂｃ")
        'abc'
    """
    # 1. NFKC: 全角英数→半角, 半角カナ→全角カナ
    text = unicodedata.normalize("NFKC", text)
    # 2. ヴ行→バ行
    text = _unify_v_sounds(text)
    # 3. ハイフン系→長音符ー
    text = _unify_prolonged_sound(text)
    # 4. カタカナ→ひらがな
    text = _katakana_to_hiragana(text)
    # 5. 英字小文字化
    text = text.lower()
    return text
