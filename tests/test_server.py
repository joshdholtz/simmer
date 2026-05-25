"""Tests for HTTP routes and input handling in server.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from simmer.backend_base import SimDevice
from simmer.server import _handle_input, make_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

IOS_DEV = SimDevice("ios-1", "iPhone 15 Pro", 393, 852)
ANDROID_DEV = SimDevice("emulator-5554", "Pixel 7", 1080, 2400)


def make_mock_backend(sims=None):
    b = MagicMock()
    b.name = "fast (quartz)"
    b.list_sims.return_value = [IOS_DEV] if sims is None else sims
    b.capture.return_value = b"\xff\xd8fake-jpeg"
    return b


@pytest.fixture
def backend():
    return make_mock_backend()


@pytest.fixture
async def client(aiohttp_client, backend):
    app = make_app(backend, fps=15, quality=70)
    return await aiohttp_client(app)


# ---------------------------------------------------------------------------
# GET /api/info
# ---------------------------------------------------------------------------


class TestInfo:
    async def test_returns_mode(self, client, backend):
        resp = await client.get("/api/info")
        assert resp.status == 200
        data = await resp.json()
        assert data["mode"] == backend.name

    async def test_returns_has_adb(self, client):
        resp = await client.get("/api/info")
        data = await resp.json()
        assert "has_adb" in data

    async def test_returns_permissions_dict(self, client):
        resp = await client.get("/api/info")
        data = await resp.json()
        assert "permissions" in data
        assert "screen_recording" in data["permissions"]
        assert "accessibility" in data["permissions"]

    async def test_bundle_id_included_when_set(self, aiohttp_client, backend):
        app = make_app(backend, bundle_id="com.example.App")
        c = await aiohttp_client(app)
        resp = await c.get("/api/info")
        data = await resp.json()
        assert data["bundle_id"] == "com.example.App"

    async def test_no_bundle_id_key_when_not_set(self, client):
        resp = await client.get("/api/info")
        data = await resp.json()
        assert "bundle_id" not in data


# ---------------------------------------------------------------------------
# GET /api/sims
# ---------------------------------------------------------------------------


class TestSims:
    async def test_returns_device_list(self, client, backend):
        resp = await client.get("/api/sims")
        assert resp.status == 200
        data = await resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "ios-1"
        assert data[0]["name"] == "iPhone 15 Pro"

    async def test_project_app_false_without_bundle_id(self, client):
        resp = await client.get("/api/sims")
        data = await resp.json()
        assert data[0]["project_app"] is False

    async def test_multiple_devices(self, aiohttp_client):
        backend = make_mock_backend(sims=[IOS_DEV, ANDROID_DEV])
        app = make_app(backend)
        c = await aiohttp_client(app)
        resp = await c.get("/api/sims")
        data = await resp.json()
        assert len(data) == 2

    async def test_empty_device_list(self, aiohttp_client):
        backend = make_mock_backend(sims=[])
        app = make_app(backend)
        c = await aiohttp_client(app)
        resp = await c.get("/api/sims")
        data = await resp.json()
        assert data == []


# ---------------------------------------------------------------------------
# GET /api/devices (available/bootable devices)
# ---------------------------------------------------------------------------


class TestDevices:
    async def test_returns_ios_devices(self, client):
        with patch(
            "simmer.server.list_available_devices",
            return_value=[
                {
                    "id": "U1",
                    "name": "iPhone 15",
                    "width": 393,
                    "height": 852,
                    "runtime": "iOS 17",
                }
            ],
        ):
            with patch("simmer.backend_base.has_adb", return_value=False):
                resp = await client.get("/api/devices")
        assert resp.status == 200
        data = await resp.json()
        assert data[0]["platform"] == "ios"
        assert data[0]["id"] == "U1"

    async def test_includes_android_when_adb_available(self, client):
        with patch("simmer.server.list_available_devices", return_value=[]):
            with patch("simmer.backend_base.has_adb", return_value=True):
                with patch(
                    "simmer.backend_adb.list_available_avds",
                    return_value=[{"avd": "Pixel_7", "name": "Pixel 7"}],
                ):
                    resp = await client.get("/api/devices")
        data = await resp.json()
        android = [d for d in data if d.get("platform") == "android"]
        assert len(android) == 1
        assert android[0]["id"] == "Pixel_7"

    async def test_excludes_android_when_no_adb(self, client):
        with patch("simmer.server.list_available_devices", return_value=[]):
            with patch("simmer.backend_base.has_adb", return_value=False):
                resp = await client.get("/api/devices")
        data = await resp.json()
        assert not any(d.get("platform") == "android" for d in data)


# ---------------------------------------------------------------------------
# POST /api/boot/<udid>
# ---------------------------------------------------------------------------


class TestBoot:
    async def test_boot_calls_boot_sim(self, client):
        with patch("simmer.server.boot_sim") as mock_boot:
            resp = await client.post("/api/boot/ios-1")
        assert resp.status == 200
        mock_boot.assert_called_once_with("ios-1")

    async def test_boot_returns_ok(self, client):
        with patch("simmer.server.boot_sim"):
            resp = await client.post("/api/boot/ios-1")
        data = await resp.json()
        assert data == {"ok": True}


# ---------------------------------------------------------------------------
# POST /api/boot-avd
# ---------------------------------------------------------------------------


class TestBootAvd:
    async def test_boot_avd_calls_boot_avd(self, client):
        with patch("simmer.backend_adb.boot_avd") as mock_boot:
            resp = await client.post(
                "/api/boot-avd",
                data=json.dumps({"avd": "Pixel_7"}),
                headers={"Content-Type": "application/json"},
            )
        assert resp.status == 200
        mock_boot.assert_called_once_with("Pixel_7")

    async def test_boot_avd_empty_avd_noop(self, client):
        with patch("simmer.backend_adb.boot_avd") as mock_boot:
            resp = await client.post(
                "/api/boot-avd",
                data=json.dumps({"avd": ""}),
                headers={"Content-Type": "application/json"},
            )
        assert resp.status == 200
        mock_boot.assert_not_called()

    async def test_boot_avd_bad_json_returns_400(self, client):
        resp = await client.post(
            "/api/boot-avd",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


# ---------------------------------------------------------------------------
# _handle_input — settings update and dispatch
# ---------------------------------------------------------------------------


class TestHandleInput:
    """_handle_input is an async function; test it directly."""

    @pytest.fixture
    def state(self):
        return {
            "fps": 15,
            "quality": 70,
            "data_saver": False,
            "dev_w": 393,
            "dev_h": 852,
        }

    @pytest.fixture
    def backend(self):
        b = MagicMock()
        b.tap = MagicMock()
        b.drag = MagicMock()
        b.key = MagicMock()
        b.text = MagicMock()
        b.home = MagicMock()
        b.rotate = MagicMock()
        b.appearance = MagicMock()
        return b

    async def test_settings_fps_clamped_low(self, state, backend):
        await _handle_input({"type": "settings", "fps": 0}, "u1", state, backend)
        assert state["fps"] == 1

    async def test_settings_fps_clamped_high(self, state, backend):
        await _handle_input({"type": "settings", "fps": 999}, "u1", state, backend)
        assert state["fps"] == 60

    async def test_settings_quality_clamped_low(self, state, backend):
        await _handle_input({"type": "settings", "quality": 5}, "u1", state, backend)
        assert state["quality"] == 10

    async def test_settings_quality_clamped_high(self, state, backend):
        await _handle_input({"type": "settings", "quality": 100}, "u1", state, backend)
        assert state["quality"] == 95

    async def test_settings_data_saver(self, state, backend):
        await _handle_input({"type": "settings", "data_saver": True}, "u1", state, backend)
        assert state["data_saver"] is True

    async def test_settings_dev_dimensions(self, state, backend):
        await _handle_input({"type": "settings", "dev_w": 1080, "dev_h": 2400}, "u1", state, backend)
        assert state["dev_w"] == 1080
        assert state["dev_h"] == 2400

    async def test_tap_dispatched(self, state, backend):
        await _handle_input({"type": "tap", "x": 0.5, "y": 0.5}, "u1", state, backend)
        backend.tap.assert_called_once_with("u1", 0.5, 0.5, 393, 852)

    async def test_drag_dispatched(self, state, backend):
        await _handle_input(
            {"type": "drag", "x1": 0.1, "y1": 0.2, "x2": 0.9, "y2": 0.8},
            "u1",
            state,
            backend,
        )
        backend.drag.assert_called_once_with("u1", 0.1, 0.2, 0.9, 0.8, 393, 852)

    async def test_key_dispatched(self, state, backend):
        await _handle_input({"type": "key", "key": "home"}, "u1", state, backend)
        backend.key.assert_called_once_with("u1", "home")

    async def test_text_dispatched(self, state, backend):
        await _handle_input({"type": "text", "text": "hello"}, "u1", state, backend)
        backend.text.assert_called_once_with("u1", "hello")

    async def test_home_dispatched(self, state, backend):
        await _handle_input({"type": "home"}, "u1", state, backend)
        backend.home.assert_called_once_with("u1")

    async def test_rotate_dispatched(self, state, backend):
        await _handle_input({"type": "rotate"}, "u1", state, backend)
        backend.rotate.assert_called_once_with("u1")

    async def test_rotate_sends_client_update_on_success(self, state, backend):
        class FakeWs:
            closed = False

            def __init__(self):
                self.messages = []

            async def send_str(self, msg):
                self.messages.append(msg)

        ws = FakeWs()
        backend.rotate.return_value = True
        await _handle_input({"type": "rotate"}, "u1", state, backend, ws)
        assert ws.messages

    async def test_rotate_does_not_update_client_on_failure(self, state, backend):
        class FakeWs:
            closed = False

            def __init__(self):
                self.messages = []

            async def send_str(self, msg):
                self.messages.append(msg)

        ws = FakeWs()
        backend.rotate.return_value = False
        await _handle_input({"type": "rotate"}, "u1", state, backend, ws)
        assert ws.messages == []

    async def test_appearance_dispatched(self, state, backend):
        await _handle_input({"type": "appearance", "mode": "dark"}, "u1", state, backend)
        backend.appearance.assert_called_once_with("u1", "dark")

    async def test_unknown_type_does_not_raise(self, state, backend):
        # Should silently ignore unknown message types
        await _handle_input({"type": "unknown_msg"}, "u1", state, backend)

    async def test_backend_exception_does_not_propagate(self, state, backend):
        backend.tap.side_effect = RuntimeError("backend crashed")
        # Must not raise — server swallows backend errors
        await _handle_input({"type": "tap", "x": 0.5, "y": 0.5}, "u1", state, backend)
