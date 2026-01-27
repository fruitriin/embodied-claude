"""Type definitions for Memory MCP Server."""

from dataclasses import dataclass
from enum import Enum


class Emotion(str, Enum):
    """感情タグ."""

    HAPPY = "happy"
    SAD = "sad"
    SURPRISED = "surprised"
    MOVED = "moved"
    EXCITED = "excited"
    NOSTALGIC = "nostalgic"
    CURIOUS = "curious"
    NEUTRAL = "neutral"


class Category(str, Enum):
    """記憶カテゴリ."""

    DAILY = "daily"
    PHILOSOPHICAL = "philosophical"
    TECHNICAL = "technical"
    MEMORY = "memory"
    OBSERVATION = "observation"
    FEELING = "feeling"
    CONVERSATION = "conversation"


@dataclass(frozen=True)
class Memory:
    """記憶データ構造."""

    id: str
    content: str
    timestamp: str  # ISO 8601 format
    emotion: str
    importance: int  # 1-5
    category: str

    def to_metadata(self) -> dict:
        """Convert to dictionary for ChromaDB metadata."""
        return {
            "timestamp": self.timestamp,
            "emotion": self.emotion,
            "importance": self.importance,
            "category": self.category,
        }


@dataclass(frozen=True)
class MemorySearchResult:
    """検索結果."""

    memory: Memory
    distance: float  # 類似度（小さいほど近い）


@dataclass(frozen=True)
class MemoryStats:
    """記憶の統計情報."""

    total_count: int
    by_category: dict[str, int]
    by_emotion: dict[str, int]
    oldest_timestamp: str | None
    newest_timestamp: str | None
