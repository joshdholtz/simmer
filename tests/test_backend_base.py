"""Tests for backend_base: logical_size, detect_bundle_id, SimDevice."""

from __future__ import annotations
import textwrap

import pytest

from simmer.backend_base import logical_size, detect_bundle_id, SimDevice


# ---------------------------------------------------------------------------
# logical_size
# ---------------------------------------------------------------------------


class TestLogicalSize:
    # Exact model matches
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("iPhone 16 Pro Max", (440, 956)),
            ("iPhone 16 Pro", (402, 874)),
            ("iPhone 16 Plus", (430, 932)),
            ("iPhone 16e", (393, 852)),
            ("iPhone 16", (393, 852)),
            ("iPhone 15 Pro Max", (430, 932)),
            ("iPhone 15 Pro", (393, 852)),
            ("iPhone 15 Plus", (430, 932)),
            ("iPhone 15", (393, 852)),
            ("iPhone 14 Pro Max", (430, 932)),
            ("iPhone 14 Pro", (393, 852)),
            ("iPhone 14 Plus", (428, 926)),
            ("iPhone 14", (390, 844)),
            ("iPhone 13 mini", (375, 812)),
            ("iPhone 13 Pro Max", (428, 926)),
            ("iPhone 13 Pro", (390, 844)),
            ("iPhone 13", (390, 844)),
            ("iPhone 12 mini", (360, 780)),
            ("iPhone 12 Pro Max", (428, 926)),
            ("iPhone 12 Pro", (390, 844)),
            ("iPhone 12", (390, 844)),
            ("iPhone SE (3rd generation)", (375, 667)),
            ("iPhone 11 Pro Max", (414, 896)),
            ("iPhone 11 Pro", (375, 812)),
            ("iPhone 11", (414, 896)),
            ("iPhone XS Max", (414, 896)),
            ("iPhone XS", (375, 812)),
            ("iPhone XR", (414, 896)),
            ("iPhone X", (375, 812)),
            ("iPhone 8 Plus", (414, 736)),
            ("iPhone 8", (375, 667)),
            ("iPad Pro (12.9-inch) (6th generation)", (1024, 1366)),
            ("iPad Pro (11-inch) (4th generation)", (834, 1194)),
            ("iPad Air (5th generation)", (820, 1180)),
            ("iPad mini (6th generation)", (744, 1133)),
            ("iPad (10th generation)", (820, 1180)),
        ],
    )
    def test_known_devices(self, name, expected):
        assert logical_size(name) == expected

    def test_case_insensitive(self):
        assert logical_size("iphone 16 pro max") == logical_size("iPhone 16 Pro Max")
        assert logical_size("IPHONE 16 PRO") == logical_size("iPhone 16 Pro")

    def test_unknown_device_returns_none(self):
        assert logical_size("Galaxy S24") is None
        assert logical_size("Pixel 9") is None
        assert logical_size("") is None

    def test_longest_prefix_wins(self):
        # "iphone 14 pro max" must not match just "iphone 14 pro" or "iphone 14"
        assert logical_size("iPhone 14 Pro Max") == (430, 932)
        assert logical_size("iPhone 14 Pro") == (393, 852)
        assert logical_size("iPhone 14") == (390, 844)

    def test_ipad_pro_12_vs_11(self):
        assert logical_size("iPad Pro (12.9-inch)") == (1024, 1366)
        assert logical_size("iPad Pro (11-inch)") == (834, 1194)

    def test_iphone_17_future_models(self):
        # Entries added for forward-compatibility
        assert logical_size("iPhone 17 Pro Max") == (440, 956)
        assert logical_size("iPhone 17 Pro") == (402, 874)
        assert logical_size("iPhone 17 Air") == (393, 852)
        assert logical_size("iPhone 17") == (393, 852)


# ---------------------------------------------------------------------------
# SimDevice
# ---------------------------------------------------------------------------


class TestSimDevice:
    def test_to_dict(self):
        d = SimDevice(udid="U1", name="iPhone 15", width=393, height=852)
        assert d.to_dict() == {
            "id": "U1",
            "name": "iPhone 15",
            "width": 393,
            "height": 852,
        }

    def test_to_dict_android_physical_pixels(self):
        # Android devices store physical pixels — large numbers are valid
        d = SimDevice(udid="emulator-5554", name="Pixel 7", width=1080, height=2400)
        assert d.to_dict()["width"] == 1080
        assert d.to_dict()["height"] == 2400


# ---------------------------------------------------------------------------
# detect_bundle_id
# ---------------------------------------------------------------------------


class TestDetectBundleId:
    def test_finds_bundle_id(self, tmp_path):
        xcodeproj = tmp_path / "MyApp.xcodeproj"
        xcodeproj.mkdir()
        pbxproj = xcodeproj / "project.pbxproj"
        pbxproj.write_text(
            textwrap.dedent("""\
            PRODUCT_BUNDLE_IDENTIFIER = com.example.MyApp;
            PRODUCT_BUNDLE_IDENTIFIER = com.example.MyAppTests;
        """)
        )
        result = detect_bundle_id(str(tmp_path))
        assert result == "com.example.MyApp"

    def test_skips_test_targets(self, tmp_path):
        xcodeproj = tmp_path / "MyApp.xcodeproj"
        xcodeproj.mkdir()
        (xcodeproj / "project.pbxproj").write_text(
            "PRODUCT_BUNDLE_IDENTIFIER = com.example.MyAppTests;\n"
            "PRODUCT_BUNDLE_IDENTIFIER = com.example.MyApp;\n"
        )
        result = detect_bundle_id(str(tmp_path))
        assert result == "com.example.MyApp"

    def test_skips_extension_targets(self, tmp_path):
        xcodeproj = tmp_path / "App.xcodeproj"
        xcodeproj.mkdir()
        (xcodeproj / "project.pbxproj").write_text(
            "PRODUCT_BUNDLE_IDENTIFIER = com.example.App.extension;\n"
            "PRODUCT_BUNDLE_IDENTIFIER = com.example.App;\n"
        )
        assert detect_bundle_id(str(tmp_path)) == "com.example.App"

    def test_skips_variable_substitution(self, tmp_path):
        xcodeproj = tmp_path / "App.xcodeproj"
        xcodeproj.mkdir()
        (xcodeproj / "project.pbxproj").write_text(
            "PRODUCT_BUNDLE_IDENTIFIER = $(PRODUCT_BUNDLE_IDENTIFIER_PREFIX).App;\n"
            "PRODUCT_BUNDLE_IDENTIFIER = com.example.RealApp;\n"
        )
        assert detect_bundle_id(str(tmp_path)) == "com.example.RealApp"

    def test_no_xcodeproj_returns_none(self, tmp_path):
        assert detect_bundle_id(str(tmp_path)) is None

    def test_empty_pbxproj_returns_none(self, tmp_path):
        xcodeproj = tmp_path / "App.xcodeproj"
        xcodeproj.mkdir()
        (xcodeproj / "project.pbxproj").write_text("")
        assert detect_bundle_id(str(tmp_path)) is None
