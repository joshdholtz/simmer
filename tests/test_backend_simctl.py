"""Tests for backend_simctl sizing and idb coordinate dimensions."""

from __future__ import annotations

from unittest.mock import patch

import simmer.backend_simctl as simctl_mod


class TestLogicalSizeFromScreenshot:
    def test_ipad_mini_scale_two(self):
        assert simctl_mod._logical_size_from_screenshot(1488, 2266) == (744, 1133)

    def test_ipad_pro_scale_two_even_when_wide(self):
        assert simctl_mod._logical_size_from_screenshot(2048, 2732) == (1024, 1366)

    def test_iphone_pro_scale_three(self):
        assert simctl_mod._logical_size_from_screenshot(1179, 2556) == (393, 852)

    def test_iphone_se_scale_two(self):
        assert simctl_mod._logical_size_from_screenshot(750, 1334) == (375, 667)


class TestSizeForDevice:
    def test_ipad_prefers_live_measurement_over_generic_name_match(self):
        with patch.object(simctl_mod, "_measure", return_value=(1032, 1376)) as measure:
            assert simctl_mod._size_for_device("iPad Pro (13-inch) (M4)", "U1") == (1032, 1376)
        measure.assert_called_once_with("U1")

    def test_ipad_falls_back_to_name_when_measurement_fails(self):
        with patch.object(simctl_mod, "_measure", return_value=None):
            assert simctl_mod._size_for_device("iPad (10th generation)", "U1") == (820, 1180)

    def test_iphone_uses_name_before_measurement(self):
        with patch.object(simctl_mod, "_measure") as measure:
            assert simctl_mod._size_for_device("iPhone 15 Pro", "U1") == (393, 852)
        measure.assert_not_called()


class TestHome:
    def test_uses_shared_ios_home_control(self):
        with patch.object(simctl_mod, "press_home", return_value=True) as press_home:
            assert simctl_mod.home("U1") is True
        press_home.assert_called_once_with("U1")
