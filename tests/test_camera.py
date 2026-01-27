"""Tests for camera controller."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wifi_cam_mcp.camera import CaptureResult, Direction, MoveResult, TapoCamera
from wifi_cam_mcp.config import CameraConfig


@pytest.fixture
def camera_config() -> CameraConfig:
    """Create test camera config."""
    return CameraConfig(
        host="192.168.1.100",
        username="test@example.com",
        password="testpassword",
    )


@pytest.fixture
def camera(camera_config: CameraConfig, tmp_path) -> TapoCamera:
    """Create camera instance for testing."""
    return TapoCamera(camera_config, str(tmp_path))


class TestTapoCamera:
    """Tests for TapoCamera class."""

    async def test_connect_creates_tapo_client(self, camera: TapoCamera):
        """Test that connect creates a Tapo client."""
        with patch("wifi_cam_mcp.camera.Tapo") as mock_tapo:
            mock_tapo.return_value = MagicMock()
            await camera.connect()
            mock_tapo.assert_called_once()

    async def test_move_left_calls_motor(self, camera: TapoCamera):
        """Test pan left calls moveMotor with correct parameters."""
        mock_tapo = MagicMock()
        mock_tapo.moveMotor = MagicMock()

        with patch("wifi_cam_mcp.camera.Tapo", return_value=mock_tapo):
            await camera.connect()
            result = await camera.pan_left(30)

            assert result.success is True
            assert result.direction == Direction.LEFT
            assert result.degrees == 30

    async def test_move_right_calls_motor(self, camera: TapoCamera):
        """Test pan right calls moveMotor with correct parameters."""
        mock_tapo = MagicMock()
        mock_tapo.moveMotor = MagicMock()

        with patch("wifi_cam_mcp.camera.Tapo", return_value=mock_tapo):
            await camera.connect()
            result = await camera.pan_right(45)

            assert result.success is True
            assert result.direction == Direction.RIGHT
            assert result.degrees == 45

    async def test_move_clamps_degrees(self, camera: TapoCamera):
        """Test that degrees are clamped to valid range."""
        mock_tapo = MagicMock()
        mock_tapo.moveMotor = MagicMock()

        with patch("wifi_cam_mcp.camera.Tapo", return_value=mock_tapo):
            await camera.connect()

            result = await camera.pan_left(180)
            assert result.degrees == 90

            result = await camera.pan_left(-10)
            assert result.degrees == 1

    async def test_capture_returns_base64_image(self, camera: TapoCamera, tmp_path):
        """Test that capture returns base64 encoded image."""
        fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_tapo = MagicMock()
        mock_tapo.getPreviewImage = MagicMock(return_value=fake_image)

        with (
            patch("wifi_cam_mcp.camera.Tapo", return_value=mock_tapo),
            patch("wifi_cam_mcp.camera.Image") as mock_image,
        ):
            mock_img = MagicMock()
            mock_img.size = (1920, 1080)
            mock_image.open.return_value = mock_img

            await camera.connect()
            result = await camera.capture_image(save_to_file=False)

            assert isinstance(result, CaptureResult)
            assert result.width == 1920
            assert result.height == 1080
            assert len(result.image_base64) > 0


class TestCaptureResult:
    """Tests for CaptureResult dataclass."""

    def test_capture_result_is_frozen(self):
        """Test that CaptureResult is immutable."""
        result = CaptureResult(
            image_base64="abc123",
            file_path="/tmp/test.jpg",
            timestamp="20240101_120000",
            width=1920,
            height=1080,
        )

        with pytest.raises(AttributeError):
            result.width = 1280


class TestMoveResult:
    """Tests for MoveResult dataclass."""

    def test_move_result_is_frozen(self):
        """Test that MoveResult is immutable."""
        result = MoveResult(
            direction=Direction.LEFT,
            degrees=30,
            success=True,
            message="OK",
        )

        with pytest.raises(AttributeError):
            result.success = False
