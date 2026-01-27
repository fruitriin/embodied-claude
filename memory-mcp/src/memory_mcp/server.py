"""MCP Server for AI Long-term Memory - Let AI remember across sessions!"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import MemoryConfig, ServerConfig
from .memory import MemoryStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryMCPServer:
    """MCP Server that gives AI long-term memory."""

    def __init__(self):
        self._server = Server("memory-mcp")
        self._memory_store: MemoryStore | None = None
        self._server_config = ServerConfig.from_env()
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up MCP tool handlers."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available memory tools."""
            return [
                Tool(
                    name="save_memory",
                    description="Save a memory to long-term storage. Use this to remember important things, experiences, conversations, or learnings.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The memory content to save",
                            },
                            "emotion": {
                                "type": "string",
                                "description": "Emotion associated with this memory",
                                "default": "neutral",
                                "enum": ["happy", "sad", "surprised", "moved", "excited", "nostalgic", "curious", "neutral"],
                            },
                            "importance": {
                                "type": "integer",
                                "description": "Importance level from 1 (trivial) to 5 (critical)",
                                "default": 3,
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "category": {
                                "type": "string",
                                "description": "Category of memory",
                                "default": "daily",
                                "enum": ["daily", "philosophical", "technical", "memory", "observation", "feeling", "conversation"],
                            },
                        },
                        "required": ["content"],
                    },
                ),
                Tool(
                    name="search_memories",
                    description="Search through memories using semantic similarity. Find memories related to a topic or query.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find related memories",
                            },
                            "n_results": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 20,
                            },
                            "emotion_filter": {
                                "type": "string",
                                "description": "Filter by emotion (optional)",
                                "enum": ["happy", "sad", "surprised", "moved", "excited", "nostalgic", "curious", "neutral"],
                            },
                            "category_filter": {
                                "type": "string",
                                "description": "Filter by category (optional)",
                                "enum": ["daily", "philosophical", "technical", "memory", "observation", "feeling", "conversation"],
                            },
                            "date_from": {
                                "type": "string",
                                "description": "Filter memories from this date (ISO 8601 format, optional)",
                            },
                            "date_to": {
                                "type": "string",
                                "description": "Filter memories until this date (ISO 8601 format, optional)",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="recall",
                    description="Automatically recall relevant memories based on the current conversation context. Use this to remember things that might be relevant.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "context": {
                                "type": "string",
                                "description": "Current conversation context or topic",
                            },
                            "n_results": {
                                "type": "integer",
                                "description": "Number of memories to recall",
                                "default": 3,
                                "minimum": 1,
                                "maximum": 10,
                            },
                        },
                        "required": ["context"],
                    },
                ),
                Tool(
                    name="list_recent_memories",
                    description="List the most recent memories. Use this to see what has been remembered recently.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of memories to list",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50,
                            },
                            "category_filter": {
                                "type": "string",
                                "description": "Filter by category (optional)",
                                "enum": ["daily", "philosophical", "technical", "memory", "observation", "feeling", "conversation"],
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="get_memory_stats",
                    description="Get statistics about stored memories. Shows total count, breakdown by category and emotion.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle tool calls."""
            if self._memory_store is None:
                return [TextContent(type="text", text="Error: Memory store not connected")]

            try:
                match name:
                    case "save_memory":
                        content = arguments.get("content", "")
                        if not content:
                            return [TextContent(type="text", text="Error: content is required")]

                        memory = await self._memory_store.save(
                            content=content,
                            emotion=arguments.get("emotion", "neutral"),
                            importance=arguments.get("importance", 3),
                            category=arguments.get("category", "daily"),
                        )

                        return [
                            TextContent(
                                type="text",
                                text=f"Memory saved!\nID: {memory.id}\nTimestamp: {memory.timestamp}\nEmotion: {memory.emotion}\nImportance: {memory.importance}\nCategory: {memory.category}",
                            )
                        ]

                    case "search_memories":
                        query = arguments.get("query", "")
                        if not query:
                            return [TextContent(type="text", text="Error: query is required")]

                        results = await self._memory_store.search(
                            query=query,
                            n_results=arguments.get("n_results", 5),
                            emotion_filter=arguments.get("emotion_filter"),
                            category_filter=arguments.get("category_filter"),
                            date_from=arguments.get("date_from"),
                            date_to=arguments.get("date_to"),
                        )

                        if not results:
                            return [TextContent(type="text", text="No memories found matching the query.")]

                        output_lines = [f"Found {len(results)} memories:\n"]
                        for i, result in enumerate(results, 1):
                            m = result.memory
                            output_lines.append(
                                f"--- Memory {i} (distance: {result.distance:.4f}) ---\n"
                                f"[{m.timestamp}] [{m.emotion}] [{m.category}] (importance: {m.importance})\n"
                                f"{m.content}\n"
                            )

                        return [TextContent(type="text", text="\n".join(output_lines))]

                    case "recall":
                        context = arguments.get("context", "")
                        if not context:
                            return [TextContent(type="text", text="Error: context is required")]

                        results = await self._memory_store.recall(
                            context=context,
                            n_results=arguments.get("n_results", 3),
                        )

                        if not results:
                            return [TextContent(type="text", text="No relevant memories found.")]

                        output_lines = [f"Recalled {len(results)} relevant memories:\n"]
                        for i, result in enumerate(results, 1):
                            m = result.memory
                            output_lines.append(
                                f"--- Memory {i} ---\n"
                                f"[{m.timestamp}] [{m.emotion}]\n"
                                f"{m.content}\n"
                            )

                        return [TextContent(type="text", text="\n".join(output_lines))]

                    case "list_recent_memories":
                        memories = await self._memory_store.list_recent(
                            limit=arguments.get("limit", 10),
                            category_filter=arguments.get("category_filter"),
                        )

                        if not memories:
                            return [TextContent(type="text", text="No memories found.")]

                        output_lines = [f"Recent {len(memories)} memories:\n"]
                        for i, m in enumerate(memories, 1):
                            output_lines.append(
                                f"--- Memory {i} ---\n"
                                f"[{m.timestamp}] [{m.emotion}] [{m.category}]\n"
                                f"{m.content}\n"
                            )

                        return [TextContent(type="text", text="\n".join(output_lines))]

                    case "get_memory_stats":
                        stats = await self._memory_store.get_stats()

                        output = f"""Memory Statistics:
Total Memories: {stats.total_count}

By Category:
{json.dumps(stats.by_category, indent=2, ensure_ascii=False)}

By Emotion:
{json.dumps(stats.by_emotion, indent=2, ensure_ascii=False)}

Date Range:
  Oldest: {stats.oldest_timestamp or 'N/A'}
  Newest: {stats.newest_timestamp or 'N/A'}
"""
                        return [TextContent(type="text", text=output)]

                    case _:
                        return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                logger.exception(f"Error in tool {name}")
                return [TextContent(type="text", text=f"Error: {e!s}")]

    async def connect_memory(self) -> None:
        """Connect to memory store."""
        config = MemoryConfig.from_env()
        self._memory_store = MemoryStore(config)
        await self._memory_store.connect()
        logger.info(f"Connected to memory store at {config.db_path}")

    async def disconnect_memory(self) -> None:
        """Disconnect from memory store."""
        if self._memory_store:
            await self._memory_store.disconnect()
            self._memory_store = None
            logger.info("Disconnected from memory store")

    @asynccontextmanager
    async def run_context(self):
        """Context manager for server lifecycle."""
        try:
            await self.connect_memory()
            yield
        finally:
            await self.disconnect_memory()

    async def run(self) -> None:
        """Run the MCP server."""
        async with self.run_context():
            async with stdio_server() as (read_stream, write_stream):
                await self._server.run(
                    read_stream,
                    write_stream,
                    self._server.create_initialization_options(),
                )


def main() -> None:
    """Entry point for the MCP server."""
    server = MemoryMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
