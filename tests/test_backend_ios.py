"""Tests for shared iOS simulator controls."""

from __future__ import annotations

from unittest.mock import patch

from conftest import make_completed_process

from simmer.backend_ios import press_home, rotate_with_xctest


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


class TestRotateWithXCTest:
    HARNESS = "/tmp/OrientationHarness.xcodeproj"

    def test_runs_xcodebuild_harness(self):
        with patch("shutil.which", return_value="/usr/bin/xcodebuild"):
            with patch("simmer.backend_ios._ensure_orientation_harness", return_value=self.HARNESS):
                with patch("subprocess.run", return_value=make_completed_process(returncode=0)) as run:
                    assert rotate_with_xctest("U1", True) is True

        assert run.call_args.args[0][:6] == [
            "xcodebuild",
            "test",
            "-project",
            "/tmp/OrientationHarness.xcodeproj",
            "-scheme",
            "OrientationHarness",
        ]
        assert (
            "-only-testing:OrientationHarnessUITests/OrientationHarnessUITests/testLandscapeLeft"
            in run.call_args.args[0]
        )

    def test_runs_portrait_test(self):
        with patch("shutil.which", return_value="/usr/bin/xcodebuild"):
            with patch("simmer.backend_ios._ensure_orientation_harness", return_value=self.HARNESS):
                with patch("subprocess.run", return_value=make_completed_process(returncode=0)) as run:
                    assert rotate_with_xctest("U1", False) is True

        assert "-only-testing:OrientationHarnessUITests/OrientationHarnessUITests/testPortrait" in run.call_args.args[0]

    def test_returns_false_when_xcodebuild_missing(self):
        with patch("shutil.which", return_value=None):
            assert rotate_with_xctest("U1", True) is False

    def test_returns_false_when_xcodebuild_fails(self):
        with patch("shutil.which", return_value="/usr/bin/xcodebuild"):
            with patch("simmer.backend_ios._ensure_orientation_harness", return_value=self.HARNESS):
                with patch("subprocess.run", return_value=make_completed_process(returncode=65)):
                    assert rotate_with_xctest("U1", True) is False
