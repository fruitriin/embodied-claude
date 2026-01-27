"""MCP Server for WiFi Camera Control - Let AI see the world!"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    ImageContent,
    TextContent,
    Tool,
)

from .camera import Direction, TapoCamera
from .config import CameraConfig, ServerConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CameraMCPServer:
    """MCP Server that gives AI eyes to see the room."""

    def __init__(self):
        self._server = Server("wifi-cam-mcp")
        self._camera: TapoCamera | None = None
        self._server_config = ServerConfig.from_env()
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up MCP tool handlers."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available camera control tools."""
            return [
                Tool(
                    name="camera_capture",
                    description="Capture a snapshot from the camera. Returns the current view as an image. Use this to see what's in front of the camera right now.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_pan_left",
                    description="Pan the camera to the LEFT. Use this when you want to look at something on the left side.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "degrees": {
                                "type": "integer",
                                "description": "Degrees to pan (1-90, default: 30)",
                                "default": 30,
                                "minimum": 1,
                                "maximum": 90,
                            }
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_pan_right",
                    description="Pan the camera to the RIGHT. Use this when you want to look at something on the right side.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "degrees": {
                                "type": "integer",
                                "description": "Degrees to pan (1-90, default: 30)",
                                "default": 30,
                                "minimum": 1,
                                "maximum": 90,
                            }
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_tilt_up",
                    description="Tilt the camera UP. Use this when you want to look at something higher up.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "degrees": {
                                "type": "integer",
                                "description": "Degrees to tilt (1-90, default: 20)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 90,
                            }
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_tilt_down",
                    description="Tilt the camera DOWN. Use this when you want to look at something lower.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "degrees": {
                                "type": "integer",
                                "description": "Degrees to tilt (1-90, default: 20)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 90,
                            }
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_look_around",
                    description="Look around the room by capturing multiple angles (center, left, right, up). Use this to get a full view of the surroundings. Returns multiple images from different angles.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_info",
                    description="Get information about the camera device.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_presets",
                    description="List saved camera position presets.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="camera_go_to_preset",
                    description="Move camera to a saved preset position.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "preset_id": {
                                "type": "string",
                                "description": "The ID of the preset to go to",
                            }
                        },
                        "required": ["preset_id"],
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent]:
            """Handle tool calls."""
            if self._camera is None:
                return [TextContent(type="text", text="Error: Camera not connected")]

            try:
                match name:
                    case "camera_capture":
                        result = await self._camera.capture_image()
                        return [
                            ImageContent(
                                type="image",
                                data=result.image_base64,
                                mimeType="image/jpeg",
                            ),
                            TextContent(
                                type="text",
                                text=f"Captured image at {result.timestamp} ({result.width}x{result.height})",
                            ),
                        ]

                    case "camera_pan_left":
                        degrees = arguments.get("degrees", 30)
                        result = await self._camera.pan_left(degrees)
                        return [TextContent(type="text", text=result.message)]

                    case "camera_pan_right":
                        degrees = arguments.get("degrees", 30)
                        result = await self._camera.pan_right(degrees)
                        return [TextContent(type="text", text=result.message)]

                    case "camera_tilt_up":
                        degrees = arguments.get("degrees", 20)
                        result = await self._camera.tilt_up(degrees)
                        return [TextContent(type="text", text=result.message)]

                    case "camera_tilt_down":
                        degrees = arguments.get("degrees", 20)
                        result = await self._camera.tilt_down(degrees)
                        return [TextContent(type="text", text=result.message)]

                    case "camera_look_around":
                        captures = await self._camera.look_around()
                        contents: list[TextContent | ImageContent] = []
                        directions = ["Center", "Left", "Right", "Up"]
                        for i, capture in enumerate(captures):
                            direction = directions[i] if i < len(directions) else f"Angle {i}"
                            contents.append(
                                TextContent(type="text", text=f"--- {direction} View ---")
                            )
                            contents.append(
                                ImageContent(
                                    type="image",
                                    data=capture.image_base64,
                                    mimeType="image/jpeg",
                                )
                            )
                        contents.append(
                            TextContent(
                                type="text",
                                text=f"Captured {len(captures)} angles. Camera returned to center position.",
                            )
                        )
                        return contents

                    case "camera_info":
                        info = await self._camera.get_device_info()
                        return [
                            TextContent(
                                type="text",
                                text=f"Camera Info:\n{json.dumps(info, indent=2)}",
                            )
                        ]

                    case "camera_presets":
                        presets = await self._camera.get_presets()
                        return [
                            TextContent(
                                type="text",
                                text=f"Camera Presets:\n{json.dumps(presets, indent=2)}",
                            )
                        ]

                    case "camera_go_to_preset":
                        preset_id = arguments.get("preset_id", "")
                        result = await self._camera.go_to_preset(preset_id)
                        return [TextContent(type="text", text=result.message)]

                    case _:
                        return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                logger.exception(f"Error in tool {name}")
                return [TextContent(type="text", text=f"Error: {e!s}")]

    async def connect_camera(self) -> None:
        """Connect to the camera."""
        config = CameraConfig.from_env()
        self._camera = TapoCamera(config, self._server_config.capture_dir)
        await self._camera.connect()
        logger.info(f"Connected to camera at {config.host}")

    async def disconnect_camera(self) -> None:
        """Disconnect from the camera."""
        if self._camera:
            await self._camera.disconnect()
            self._camera = None
            logger.info("Disconnected from camera")

    @asynccontextmanager
    async def run_context(self):
        """Context manager for server lifecycle."""
        try:
            await self.connect_camera()
            yield
        finally:
            await self.disconnect_camera()

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
    server = CameraMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
