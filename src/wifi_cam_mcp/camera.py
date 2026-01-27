"""Tapo Camera Controller - The eyes of AI."""

import asyncio
import base64
import io
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from PIL import Image
from pytapo import Tapo

from .config import CameraConfig


class Direction(str, Enum):
    """Pan/Tilt directions."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class CaptureResult:
    """Result of image capture."""

    image_base64: str
    file_path: str | None
    timestamp: str
    width: int
    height: int


@dataclass(frozen=True)
class MoveResult:
    """Result of camera movement."""

    direction: Direction
    degrees: int
    success: bool
    message: str


class TapoCamera:
    """Controller for Tapo C210 and similar PTZ cameras."""

    def __init__(self, config: CameraConfig, capture_dir: str = "/tmp/wifi-cam-mcp"):
        self._config = config
        self._capture_dir = Path(capture_dir)
        self._tapo: Tapo | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish connection to camera."""
        async with self._lock:
            if self._tapo is None:
                self._tapo = await asyncio.to_thread(
                    Tapo,
                    self._config.host,
                    self._config.username,
                    self._config.password,
                )
                self._capture_dir.mkdir(parents=True, exist_ok=True)

    async def disconnect(self) -> None:
        """Close connection to camera."""
        async with self._lock:
            self._tapo = None

    def _ensure_connected(self) -> Tapo:
        """Ensure camera is connected and return client."""
        if self._tapo is None:
            raise RuntimeError("Camera not connected. Call connect() first.")
        return self._tapo

    async def capture_image(self, save_to_file: bool = True) -> CaptureResult:
        """
        Capture a snapshot from the camera.

        Args:
            save_to_file: If True, save image to disk as well

        Returns:
            CaptureResult with base64 encoded image and metadata
        """
        tapo = self._ensure_connected()

        image_data = await asyncio.to_thread(tapo.getPreviewImage)

        image = Image.open(io.BytesIO(image_data))
        width, height = image.size

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_base64 = base64.standard_b64encode(buffer.getvalue()).decode("utf-8")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = None

        if save_to_file:
            file_path = str(self._capture_dir / f"capture_{timestamp}.jpg")
            with open(file_path, "wb") as f:
                f.write(image_data)

        return CaptureResult(
            image_base64=image_base64,
            file_path=file_path,
            timestamp=timestamp,
            width=width,
            height=height,
        )

    async def move(self, direction: Direction, degrees: int = 30) -> MoveResult:
        """
        Move the camera in specified direction.

        Args:
            direction: Direction to move (left, right, up, down)
            degrees: Degrees to move (default: 30)

        Returns:
            MoveResult with operation status
        """
        tapo = self._ensure_connected()
        degrees = max(1, min(degrees, 90))

        try:
            match direction:
                case Direction.LEFT:
                    await asyncio.to_thread(tapo.moveMotor, 0, -degrees)
                case Direction.RIGHT:
                    await asyncio.to_thread(tapo.moveMotor, 0, degrees)
                case Direction.UP:
                    await asyncio.to_thread(tapo.moveMotor, degrees, 0)
                case Direction.DOWN:
                    await asyncio.to_thread(tapo.moveMotor, -degrees, 0)

            await asyncio.sleep(0.5)

            return MoveResult(
                direction=direction,
                degrees=degrees,
                success=True,
                message=f"Moved {direction.value} by {degrees} degrees",
            )
        except Exception as e:
            return MoveResult(
                direction=direction,
                degrees=degrees,
                success=False,
                message=f"Failed to move: {e!s}",
            )

    async def pan_left(self, degrees: int = 30) -> MoveResult:
        """Pan camera to the left."""
        return await self.move(Direction.LEFT, degrees)

    async def pan_right(self, degrees: int = 30) -> MoveResult:
        """Pan camera to the right."""
        return await self.move(Direction.RIGHT, degrees)

    async def tilt_up(self, degrees: int = 20) -> MoveResult:
        """Tilt camera upward."""
        return await self.move(Direction.UP, degrees)

    async def tilt_down(self, degrees: int = 20) -> MoveResult:
        """Tilt camera downward."""
        return await self.move(Direction.DOWN, degrees)

    async def look_around(self) -> list[CaptureResult]:
        """
        Look around the room by capturing multiple angles.

        Captures: center, left, right, up-center positions.

        Returns:
            List of CaptureResults from different angles
        """
        captures: list[CaptureResult] = []

        center = await self.capture_image()
        captures.append(center)

        await self.pan_left(45)
        left = await self.capture_image()
        captures.append(left)

        await self.pan_right(90)
        right = await self.capture_image()
        captures.append(right)

        await self.pan_left(45)
        await self.tilt_up(20)
        up = await self.capture_image()
        captures.append(up)

        await self.tilt_down(20)

        return captures

    async def get_device_info(self) -> dict:
        """Get camera device information."""
        tapo = self._ensure_connected()
        info = await asyncio.to_thread(tapo.getBasicInfo)
        return info.get("device_info", {}).get("basic_info", {})

    async def get_presets(self) -> list[dict]:
        """Get saved camera presets."""
        tapo = self._ensure_connected()
        presets = await asyncio.to_thread(tapo.getPresets)
        return presets

    async def go_to_preset(self, preset_id: str) -> MoveResult:
        """Move camera to a saved preset position."""
        tapo = self._ensure_connected()
        try:
            await asyncio.to_thread(tapo.setPreset, preset_id)
            await asyncio.sleep(1)
            return MoveResult(
                direction=Direction.LEFT,
                degrees=0,
                success=True,
                message=f"Moved to preset {preset_id}",
            )
        except Exception as e:
            return MoveResult(
                direction=Direction.LEFT,
                degrees=0,
                success=False,
                message=f"Failed to go to preset: {e!s}",
            )
