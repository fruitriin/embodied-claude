# memory-mcp

MCP server for AI long-term memory - Let AI remember across sessions!

## Overview

This MCP server provides long-term memory capabilities for AI assistants using ChromaDB for vector storage. Memories are stored with semantic embeddings, allowing for intelligent recall based on context.

## Features

- **Semantic Memory Storage**: Save memories with emotion tags, importance levels, and categories
- **Semantic Search**: Find relevant memories using natural language queries
- **Context-based Recall**: Automatically recall memories relevant to the current conversation
- **Persistent Storage**: Memories are stored locally and persist across sessions
- **Statistics**: Track memory counts by category and emotion

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/memory-mcp.git
cd memory-mcp

# Install dependencies
uv sync

# Run the server
uv run memory-mcp
```

## Configuration

Set these environment variables or create a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_DB_PATH` | `~/.claude/memories/chroma` | ChromaDB storage path |
| `MEMORY_COLLECTION_NAME` | `claude_memories` | Collection name |

## Tools

### save_memory

Save a memory to long-term storage.

```json
{
  "content": "Today I learned about vector databases",
  "emotion": "excited",
  "importance": 4,
  "category": "technical"
}
```

### search_memories

Search memories by semantic similarity.

```json
{
  "query": "things I learned about databases",
  "n_results": 5,
  "category_filter": "technical"
}
```

### recall

Recall relevant memories based on conversation context.

```json
{
  "context": "We were discussing database optimization",
  "n_results": 3
}
```

### list_recent_memories

List the most recent memories.

```json
{
  "limit": 10,
  "category_filter": "memory"
}
```

### get_memory_stats

Get statistics about stored memories.

## Claude Code Integration

Add to your `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/memory-mcp", "memory-mcp"]
    }
  }
}
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Lint
uv run ruff check src/
```

## License

MIT
