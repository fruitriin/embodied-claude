#!/usr/bin/env python3
"""ChromaDB の埋め込みを intfloat/multilingual-e5-base に移行するスクリプト。

使い方:
    cd memory-mcp
    uv run python scripts/migrate_embeddings.py

注意:
    - 既存の all-MiniLM-L6-v2 (384次元) から multilingual-e5-base (768次元) に移行
    - 実行後は元のモデルとの互換性なし
    - バックアップを取ってから実行することを推奨
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memory_mcp.config import MemoryConfig
from memory_mcp.embedding import E5EmbeddingFunction
from memory_mcp.normalizer import normalize_japanese


async def migrate(config: MemoryConfig) -> None:
    """ChromaDB の全記憶を e5 モデルで再 embedding する。"""
    import chromadb

    print(f"DB パス: {config.db_path}")
    print(f"コレクション名: {config.collection_name}")
    print()

    # 元のコレクション（旧モデル）から全データを取得
    client = chromadb.PersistentClient(path=config.db_path)

    try:
        old_collection = client.get_collection(name=config.collection_name)
    except Exception:
        print(f"コレクション '{config.collection_name}' が見つかりません。")
        return

    result = old_collection.get(include=["documents", "metadatas"])
    ids = result.get("ids", [])
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []

    if not ids:
        print("記憶が0件です。移行不要。")
        return

    print(f"移行対象: {len(ids)} 件")

    # e5 埋め込み関数を初期化
    print("モデルをロード中...")
    ef = E5EmbeddingFunction(config.embedding_model)
    ef._load_model()
    print(f"モデル '{config.embedding_model}' のロード完了")
    print()

    # バックアップコレクション名（念のため）
    backup_name = f"{config.collection_name}_backup_pre_e5"
    try:
        client.delete_collection(backup_name)
    except Exception:
        pass

    # 元のコレクション削除（旧次元数とは互換性がないため）
    print("旧コレクションを削除して新コレクションを作成...")
    client.delete_collection(config.collection_name)

    # 新コレクション作成（e5 埋め込み関数で）
    new_collection = client.create_collection(
        name=config.collection_name,
        embedding_function=ef,
        metadata={"description": "Claude's long-term memories", "embedding_model": config.embedding_model},
    )

    # バッチで再 embedding して追加
    batch_size = 32
    total = len(ids)
    for i in range(0, total, batch_size):
        batch_ids = ids[i : i + batch_size]
        batch_docs = documents[i : i + batch_size]
        batch_metas = metadatas[i : i + batch_size]

        # 正規化済みテキストで embedding
        normalized_docs = [normalize_japanese(doc) if doc else doc for doc in batch_docs]

        new_collection.add(
            ids=batch_ids,
            documents=normalized_docs,
            metadatas=batch_metas,
        )

        done = min(i + batch_size, total)
        print(f"  {done}/{total} 件完了", end="\r", flush=True)

    print(f"\n移行完了: {total} 件を '{config.embedding_model}' で再 embedding しました。")
    print("新コレクション次元数: 768次元")


def main() -> None:
    config = MemoryConfig.from_env()
    config = MemoryConfig(
        db_path=config.db_path,
        collection_name=config.collection_name,
        embedding_model="intfloat/multilingual-e5-base",
    )
    asyncio.run(migrate(config))


if __name__ == "__main__":
    main()
