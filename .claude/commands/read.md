---
description: "Web ページの本文をリーダーモードで読み取る。WebFetch と違い、AI による要約を挟まず生テキストを返す。物語や記事をじっくり読むときに使う。"
argument-hint: "<URL>"
allowed-tools: Bash(bun run scripts/reader.ts:*)
---

Web ページの本文をリーダーモードで読み取る。WebFetch と違い、AI による要約を挟まず生テキストを返す。物語や記事をじっくり読むときに使う。

## 使い方

- `/read https://example.com/article` → 本文全文を表示
- `/read https://ncode.syosetu.com/n8725k/16/` → なろう小説の1話分を表示

## 実行方法

`bun run scripts/reader.ts` を実行する。

```bash
# 全文取得
bun run scripts/reader.ts "<URL>"

# ページ情報のみ
bun run scripts/reader.ts "<URL>" --info

# 特定ページだけ取得（長い場合）
bun run scripts/reader.ts "<URL>" --page 1
```

## 手順

1. 入力から URL を抽出する
2. まず `--info` で長さを確認する
3. 短い場合（5ページ以下）はそのまま全文取得
4. 長い場合はページごとに `--page N` で分割取得
5. 取得したテキストをそのまま読む。要約しない

## 注意

- これは「読書」のためのツール。情報検索ではなく物語を味わうために使う
- 取得したテキストを勝手に要約しないこと

## エラーハンドリング

実行時に依存パッケージが見つからないエラーが出た場合:

```bash
cd scripts
bun install @mozilla/readability linkedom
```

初回実行時や、パッケージが不足している場合は上記コマンドでインストールが必要。

入力: $ARGUMENTS
