"""Tests for MultiBackend: routing, aggregation, error isolation."""

from __future__ import annotations

from unittest.mock import MagicMock

from simmer.backend_base import SimDevice
from simmer.backend_multi import MultiBackend


def make_backend(name, devices=None):
    b = MagicMock()
    b.name = name
    b.list_sims.return_value = devices or []
    b.capture.return_value = b"frame"
    return b


IOS_DEV = SimDevice("ios-udid-1", "iPhone 15 Pro", 393, 852)
ANDROID_DEV = SimDevice("emulator-5554", "Pixel 7", 1080, 2400)


# ---------------------------------------------------------------------------
# name property
# ---------------------------------------------------------------------------


class TestMultiBackendName:
    def test_joins_backend_names(self):
        mb = MultiBackend([make_backend("fast (quartz)"), make_backend("android (adb)")])
        assert mb.name == "fast (quartz) + android (adb)"

    def test_single_backend(self):
        mb = MultiBackend([make_backend("fast (quartz)")])
        assert mb.name == "fast (quartz)"


# ---------------------------------------------------------------------------
# list_sims — aggregation and UDID routing
# ---------------------------------------------------------------------------


class TestListSims:
    def test_aggregates_from_all_backends(self):
        ios = make_backend("fast", [IOS_DEV])
        android = make_backend("android", [ANDROID_DEV])
        mb = MultiBackend([ios, android])

        sims = mb.list_sims()
        udids = {s.udid for s in sims}
        assert "ios-udid-1" in udids
        assert "emulator-5554" in udids

    def test_one_backend_failing_does_not_break_other(self):
        ios = make_backend("fast", [IOS_DEV])
        broken = make_backend("broken")
        broken.list_sims.side_effect = RuntimeError("adb not found")

        mb = MultiBackend([ios, broken])
        sims = mb.list_sims()
        assert any(s.udid == "ios-udid-1" for s in sims)

    def test_udid_map_built_after_list_sims(self):
        ios = make_backend("fast", [IOS_DEV])
        android = make_backend("android", [ANDROID_DEV])
        mb = MultiBackend([ios, android])

        mb.list_sims()
        assert mb._backend_for("ios-udid-1") is ios
        assert mb._backend_for("emulator-5554") is android

    def test_atomic_map_swap(self):
        """After a second list_sims call the map should reflect the new state."""
        ios = make_backend("fast", [IOS_DEV])
        mb = MultiBackend([ios])

        mb.list_sims()
        assert mb._backend_for("ios-udid-1") is ios

        new_dev = SimDevice("ios-udid-2", "iPhone 16", 393, 852)
        ios.list_sims.return_value = [new_dev]
        mb.list_sims()

        assert mb._backend_for("ios-udid-2") is ios

    def test_both_backends_called_in_parallel(self):
        """Both backends' list_sims must be called (parallel execution)."""
        ios = make_backend("fast", [IOS_DEV])
        android = make_backend("android", [ANDROID_DEV])
        mb = MultiBackend([ios, android])
        mb.list_sims()
        ios.list_sims.assert_called_once()
        android.list_sims.assert_called_once()


# ---------------------------------------------------------------------------
# Routing — each call goes to the correct sub-backend
# ---------------------------------------------------------------------------


class TestRouting:
    def setup_method(self):
        self.ios = make_backend("fast", [IOS_DEV])
        self.android = make_backend("android", [ANDROID_DEV])
        self.mb = MultiBackend([self.ios, self.android])
        self.mb.list_sims()  # populate udid map

    def test_capture_routes_to_ios(self):
        self.mb.capture("ios-udid-1", 70)
        self.ios.capture.assert_called_once_with("ios-udid-1", 70)
        self.android.capture.assert_not_called()

    def test_capture_routes_to_android(self):
        self.mb.capture("emulator-5554", 70)
        self.android.capture.assert_called_once_with("emulator-5554", 70)
        self.ios.capture.assert_not_called()

    def test_tap_routes_correctly(self):
        self.mb.tap("emulator-5554", 0.5, 0.5, 1080, 2400)
        self.android.tap.assert_called_once_with("emulator-5554", 0.5, 0.5, 1080, 2400)
        self.ios.tap.assert_not_called()

    def test_drag_routes_correctly(self):
        self.mb.drag("ios-udid-1", 0.1, 0.2, 0.9, 0.8, 393, 852)
        self.ios.drag.assert_called_once_with("ios-udid-1", 0.1, 0.2, 0.9, 0.8, 393, 852)

    def test_key_routes_correctly(self):
        self.mb.key("emulator-5554", "home")
        self.android.key.assert_called_once_with("emulator-5554", "home")

    def test_text_routes_correctly(self):
        self.mb.text("ios-udid-1", "hello")
        self.ios.text.assert_called_once_with("ios-udid-1", "hello")

    def test_home_routes_correctly(self):
        self.android.home.return_value = True
        assert self.mb.home("emulator-5554") is True
        self.android.home.assert_called_once_with("emulator-5554")

    def test_rotate_routes_correctly(self):
        self.ios.rotate.return_value = True
        assert self.mb.rotate("ios-udid-1") is True
        self.ios.rotate.assert_called_once_with("ios-udid-1")

    def test_appearance_routes_correctly(self):
        self.mb.appearance("emulator-5554", "dark")
        self.android.appearance.assert_called_once_with("emulator-5554", "dark")


# ---------------------------------------------------------------------------
# _backend_for — fallback behaviour
# ---------------------------------------------------------------------------


class TestBackendFor:
    def test_unknown_udid_triggers_refresh_then_falls_back(self):
        """If UDID isn't in the map, list_sims() is called once, then falls back to backends[0]."""
        ios = make_backend("fast", [])
        mb = MultiBackend([ios])
        # Map is empty — _backend_for should call list_sims() as a fallback
        result = mb._backend_for("nonexistent-udid")
        ios.list_sims.assert_called_once()
        assert result is ios  # falls back to first backend

    def test_returns_correct_after_cache_miss_and_refresh(self):
        """After refresh via _backend_for, the correct backend is returned."""
        android = make_backend("android", [ANDROID_DEV])
        ios = make_backend("fast", [IOS_DEV])
        mb = MultiBackend([ios, android])
        # Don't pre-populate with list_sims — let _backend_for trigger it
        result = mb._backend_for("emulator-5554")
        assert result is android
