"""Tests for shared iOS simulator controls."""

from __future__ import annotations

from unittest.mock import patch

from conftest import make_completed_process

from simmer.backend_ios import press_home


class TestPressHome:
    def test_uses_idb_home_button_when_available(self):
        with patch("shutil.which", return_value="/usr/local/bin/idb"):
            with patch("subprocess.run", return_value=make_completed_process(returncode=0)) as run:
                assert press_home("U1") is True

        run.assert_called_once_with(
            ["/usr/local/bin/idb", "ui", "button", "HOME", "--udid", "U1"],
            capture_output=True,
            timeout=5,
        )

    def test_falls_back_to_springboard_when_idb_fails(self):
        with patch("shutil.which", return_value="/usr/local/bin/idb"):
            with patch("subprocess.run") as run:
                run.side_effect = [
                    make_completed_process(returncode=1),
                    make_completed_process(returncode=0),
                ]
                assert press_home("U1") is True

        assert run.call_args_list[1].args[0] == ["xcrun", "simctl", "launch", "U1", "com.apple.springboard"]

    def test_uses_springboard_when_idb_missing(self):
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run", return_value=make_completed_process(returncode=0)) as run:
                assert press_home("U1") is True

        run.assert_called_once_with(
            ["xcrun", "simctl", "launch", "U1", "com.apple.springboard"],
            capture_output=True,
            timeout=5,
        )

    def test_returns_false_when_all_methods_fail(self):
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run", return_value=make_completed_process(returncode=1)):
                assert press_home("U1") is False
