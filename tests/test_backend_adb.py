"""Tests for backend_adb: parsing, coordinate math, text escaping, device routing."""

from __future__ import annotations
from unittest.mock import patch

import pytest

import simmer.backend_adb as adb_mod
from simmer.backend_adb import (
    _parse_size,
    AdbBackend,
)
from conftest import make_completed_process


# ---------------------------------------------------------------------------
# _parse_size
# ---------------------------------------------------------------------------


class TestParseSize:
    def test_standard_output(self):
        assert _parse_size("Physical size: 1080x2400") == (1080, 2400)

    def test_override_size_line(self):
        # wm size can return "Override size: WxH" after "Physical size: WxH"
        text = "Physical size: 1080x2400\nOverride size: 1080x2400"
        assert _parse_size(text) == (1080, 2400)

    def test_plain_dimensions(self):
        assert _parse_size("1440x3200") == (1440, 3200)

    def test_no_match_returns_none(self):
        assert _parse_size("") is None
        assert _parse_size("no dimensions here") is None

    def test_first_match_wins(self):
        result = _parse_size("800x600\n1080x2400")
        assert result == (800, 600)


# ---------------------------------------------------------------------------
# _find_adb — prefers SDK over PATH
# ---------------------------------------------------------------------------


class TestFindAdb:
    def test_prefers_sdk_adb_over_path(self, tmp_path):
        sdk_adb = tmp_path / "platform-tools" / "adb"
        sdk_adb.parent.mkdir()
        sdk_adb.touch()

        sdk_roots = [str(tmp_path), "", ""]
        with patch.object(adb_mod, "_SDK_ROOTS", sdk_roots):
            result = adb_mod._find_adb()
        assert result == str(sdk_adb)

    def test_falls_back_to_which(self, tmp_path):
        sdk_roots = [str(tmp_path / "nonexistent"), "", ""]
        with patch.object(adb_mod, "_SDK_ROOTS", sdk_roots):
            with patch("shutil.which", return_value="/usr/local/bin/adb"):
                result = adb_mod._find_adb()
        assert result == "/usr/local/bin/adb"


# ---------------------------------------------------------------------------
# list_sims — adb output parsing
# ---------------------------------------------------------------------------

ADB_DEVICES_OUTPUT = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\toffline\n192.168.1.100:5555\tdevice\n"

WM_SIZE_1080x2400 = b"Physical size: 1080x2400\n"
WM_SIZE_1440x3200 = b"Physical size: 1440x3200\n"

AVD_NAME_OUTPUT = b"Pixel_7\nOK\n"

# adb devices uses text=True → stdout is a string
_DEVICES_RESULT = make_completed_process(stdout=ADB_DEVICES_OUTPUT)


class TestListSims:
    # Call order within list_sims for one emulator:
    #   1. subprocess.run([_ADB, "devices"], text=True)  → string stdout
    #   2. _adb(serial, "shell", "wm", "size")           → bytes stdout
    #   3. _adb(serial, "emu", "avd", "name") [in _device_name] → bytes stdout

    def test_parses_running_emulators(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _DEVICES_RESULT,
                make_completed_process(stdout=WM_SIZE_1080x2400),  # wm size
                make_completed_process(stdout=AVD_NAME_OUTPUT),  # emu avd name
            ]
            sims = adb_mod.list_sims()

        assert len(sims) == 1
        assert sims[0].udid == "emulator-5554"

    def test_filters_offline_and_non_emulator(self):
        # emulator-5556 is offline, 192.168.1.100:5555 is not an emulator serial
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _DEVICES_RESULT,
                make_completed_process(stdout=WM_SIZE_1080x2400),
                make_completed_process(stdout=AVD_NAME_OUTPUT),
            ]
            sims = adb_mod.list_sims()

        udids = [s.udid for s in sims]
        assert "emulator-5556" not in udids
        assert "192.168.1.100:5555" not in udids

    def test_physical_pixels_stored_portrait(self):
        """Width must be min(pw,ph) and height max — physical pixels, portrait orientation."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _DEVICES_RESULT,
                make_completed_process(stdout=WM_SIZE_1080x2400),
                make_completed_process(stdout=AVD_NAME_OUTPUT),
            ]
            sims = adb_mod.list_sims()

        assert sims[0].width == 1080
        assert sims[0].height == 2400

    def test_landscape_dimensions_normalized(self):
        """If adb reports landscape dimensions they are swapped to portrait (min=w, max=h)."""
        landscape_output = b"Physical size: 2400x1080\n"
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                _DEVICES_RESULT,
                make_completed_process(stdout=landscape_output),
                make_completed_process(stdout=AVD_NAME_OUTPUT),
            ]
            sims = adb_mod.list_sims()

        assert sims[0].width == 1080  # min
        assert sims[0].height == 2400  # max

    def test_empty_device_list(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = make_completed_process(
                stdout="List of devices attached\n"  # text=True → string
            )
            sims = adb_mod.list_sims()
        assert sims == []

    def test_adb_not_available(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            sims = adb_mod.list_sims()
        assert sims == []


# ---------------------------------------------------------------------------
# AdbBackend.tap — physical pixel coordinate math (the key gotcha)
# ---------------------------------------------------------------------------


class TestAdbBackendTap:
    """Tap coordinates must be physical pixels with no density conversion."""

    def _tap_args(self, nx, ny, dev_w, dev_h):
        captured = []

        def fake_adb(serial, *args, **kwargs):
            captured.extend(args)
            return make_completed_process()

        with patch.object(adb_mod, "_adb", side_effect=fake_adb):
            AdbBackend().tap("emulator-5554", nx, ny, dev_w, dev_h)
        return captured

    def test_center(self):
        args = self._tap_args(0.5, 0.5, 1080, 2400)
        assert "540" in args
        assert "1200" in args

    def test_top_left(self):
        args = self._tap_args(0.0, 0.0, 1080, 2400)
        assert "0" in args

    def test_bottom_right(self):
        args = self._tap_args(1.0, 1.0, 1080, 2400)
        assert "1080" in args
        assert "2400" in args

    def test_no_density_factor(self):
        # At 2.625x density, wrong code would multiply by ~2.625.
        # Correct code: x = int(0.25 * 1080) = 270, not 270 * 2.625 = 709
        args = self._tap_args(0.25, 0.25, 1080, 2400)
        assert "270" in args
        assert "600" in args

    def test_fractional_truncation(self):
        # int() truncation, not rounding
        args = self._tap_args(1 / 3, 1 / 3, 1080, 2400)
        assert str(int(1 / 3 * 1080)) in args
        assert str(int(1 / 3 * 2400)) in args


# ---------------------------------------------------------------------------
# AdbBackend.drag
# ---------------------------------------------------------------------------


class TestAdbBackendDrag:
    def _drag_args(self, nx1, ny1, nx2, ny2, dev_w=1080, dev_h=2400):
        captured = []

        def fake_adb(serial, *args, **kwargs):
            captured.extend(args)
            return make_completed_process()

        with patch.object(adb_mod, "_adb", side_effect=fake_adb):
            AdbBackend().drag("emulator-5554", nx1, ny1, nx2, ny2, dev_w, dev_h)
        return captured

    def test_swipe_down(self):
        args = self._drag_args(0.5, 0.2, 0.5, 0.8, 1080, 2400)
        assert "540" in args  # x1 = x2 = center
        assert "480" in args  # y1 = int(0.2 * 2400)
        assert "1920" in args  # y2 = int(0.8 * 2400)

    def test_includes_duration(self):
        args = self._drag_args(0.0, 0.0, 1.0, 1.0)
        assert "300" in args  # swipe duration ms


# ---------------------------------------------------------------------------
# AdbBackend.text — shell escaping
# ---------------------------------------------------------------------------


class TestAdbBackendText:
    def _sent_text(self, input_text):
        captured = []

        def fake_adb(serial, *args, **kwargs):
            captured.extend(args)
            return make_completed_process()

        with patch.object(adb_mod, "_adb", side_effect=fake_adb):
            AdbBackend().text("emulator-5554", input_text)
        # The last element is the escaped text argument
        return captured[-1]

    def test_spaces_become_percent_s(self):
        assert self._sent_text("hello world") == "hello%sworld"

    def test_backslash_escaped(self):
        assert self._sent_text("C:\\path") == "C:\\\\path"

    def test_double_quotes_escaped(self):
        result = self._sent_text('say "hi"')
        assert '\\"' in result

    def test_single_quotes_escaped(self):
        result = self._sent_text("it's fine")
        assert "\\'" in result

    def test_plain_text_unchanged(self):
        assert self._sent_text("hello") == "hello"

    def test_multiple_spaces(self):
        assert self._sent_text("a b c") == "a%sb%sc"


# ---------------------------------------------------------------------------
# AdbBackend.key — keymap
# ---------------------------------------------------------------------------


class TestAdbBackendKey:
    def _sent_keyevent(self, key):
        captured = []

        def fake_adb(serial, *args, **kwargs):
            captured.extend(args)
            return make_completed_process()

        with patch.object(adb_mod, "_adb", side_effect=fake_adb):
            AdbBackend().key("emulator-5554", key)
        return captured

    @pytest.mark.parametrize(
        "key,expected_code",
        [
            ("home", "KEYCODE_HOME"),
            ("back", "KEYCODE_BACK"),
            ("return", "KEYCODE_ENTER"),
            ("delete", "KEYCODE_DEL"),
            ("escape", "KEYCODE_ESCAPE"),
            ("space", "KEYCODE_SPACE"),
            ("tab", "KEYCODE_TAB"),
        ],
    )
    def test_mapped_keys(self, key, expected_code):
        args = self._sent_keyevent(key)
        assert expected_code in args

    def test_unmapped_key_sends_nothing(self):
        called = []
        with patch.object(
            adb_mod, "_adb", side_effect=lambda *a, **k: called.append(a)
        ):
            AdbBackend().key("emulator-5554", "unknownkey")
        assert not called

    def test_case_insensitive(self):
        args = self._sent_keyevent("HOME")
        assert "KEYCODE_HOME" in args


# ---------------------------------------------------------------------------
# AdbBackend.rotate — cycles 0→1→2→3→0
# ---------------------------------------------------------------------------


class TestAdbBackendRotate:
    def _do_rotate(self, current_rotation):
        sent = []

        def fake_adb(serial, *args, **kwargs):
            if "get" in args:
                r = make_completed_process(stdout=str(current_rotation).encode())
            else:
                sent.append(args[-1])  # last arg is the new rotation value
                r = make_completed_process()
            return r

        with patch.object(adb_mod, "_adb", side_effect=fake_adb):
            AdbBackend().rotate("emulator-5554")
        return sent[0] if sent else None

    def test_0_becomes_1(self):
        assert self._do_rotate(0) == "1"

    def test_1_becomes_2(self):
        assert self._do_rotate(1) == "2"

    def test_2_becomes_3(self):
        assert self._do_rotate(2) == "3"

    def test_3_wraps_to_0(self):
        assert self._do_rotate(3) == "0"


# ---------------------------------------------------------------------------
# AdbBackend.appearance
# ---------------------------------------------------------------------------


class TestAdbBackendAppearance:
    def _night_arg(self, mode):
        captured = []

        def fake_adb(serial, *args, **kwargs):
            captured.extend(args)
            return make_completed_process()

        with patch.object(adb_mod, "_adb", side_effect=fake_adb):
            AdbBackend().appearance("emulator-5554", mode)
        return captured

    def test_dark_sends_yes(self):
        assert "yes" in self._night_arg("dark")

    def test_light_sends_no(self):
        assert "no" in self._night_arg("light")


# ---------------------------------------------------------------------------
# list_available_avds — excludes running emulators
# ---------------------------------------------------------------------------


class TestListAvailableAvds:
    def test_excludes_running(self):
        running_serial = "emulator-5554"
        # list_available_avds calls list_sims() then subprocess.run([_EMULATOR, "-list-avds"], text=True)
        with patch.object(
            adb_mod,
            "list_sims",
            return_value=[
                __import__("simmer.backend_base", fromlist=["SimDevice"]).SimDevice(
                    udid=running_serial, name="Pixel 7", width=1080, height=2400
                )
            ],
        ):
            with patch("subprocess.run") as mock_run:
                # text=True → string stdout
                mock_run.return_value = make_completed_process(
                    stdout="Pixel_7\nPixel_6\n"
                )
                result = adb_mod.list_available_avds()

        names = [a["avd"] for a in result]
        assert "Pixel_7" not in names
        assert "Pixel_6" in names

    def test_replaces_underscores_with_spaces(self):
        with patch.object(adb_mod, "list_sims", return_value=[]):
            with patch("subprocess.run") as mock_run:
                # text=True → string stdout
                mock_run.return_value = make_completed_process(stdout="My_AVD_Name\n")
                result = adb_mod.list_available_avds()
        assert result[0]["name"] == "My AVD Name"
