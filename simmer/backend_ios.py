from __future__ import annotations

# ruff: noqa: E501
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent

_ROTATE_LOG = "/tmp/simmer_rotate.log"


def _rlog(*args) -> None:
    import datetime

    msg = " ".join(str(a) for a in args)
    line = f"{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]} {msg}\n"
    print(line, end="", flush=True)
    try:
        with open(_ROTATE_LOG, "a") as f:
            f.write(line)
    except Exception:
        pass


def press_home(udid: str) -> bool:
    """Press iOS Simulator Home without relying on macOS Accessibility.

    idb's HOME button is the closest simulator-level input. If idb is not
    available or its companion is not connected, launching SpringBoard is a
    practical simctl fallback that returns the device to the home screen.
    """
    idb = shutil.which("idb")
    if idb:
        try:
            result = subprocess.run(
                [idb, "ui", "button", "HOME", "--udid", udid],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["xcrun", "simctl", "launch", udid, "com.apple.springboard"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _harness_root() -> Path:
    return Path.home() / "Library" / "Caches" / "simmer" / "orientation_harness_v1"


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == content:
        return
    path.write_text(content)


def _ensure_orientation_harness() -> Path:
    root = _harness_root()
    xcodeproj = root / "OrientationHarness.xcodeproj"
    _write_if_changed(
        root / "App.swift",
        dedent(
            """
            import UIKit

            final class RootViewController: UIViewController {
              override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .all }
              override var shouldAutorotate: Bool { true }
            }

            @main
            class AppDelegate: UIResponder, UIApplicationDelegate {
              var window: UIWindow?
              func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
                window = UIWindow(frame: UIScreen.main.bounds)
                let vc = RootViewController()
                vc.view.backgroundColor = .black
                window?.rootViewController = vc
                window?.makeKeyAndVisible()
                return true
              }
            }
            """
        ).strip()
        + "\n",
    )
    _write_if_changed(
        root / "OrientationHarnessUITests.swift",
        dedent(
            """
            import XCTest

            final class OrientationHarnessUITests: XCTestCase {
              func testLandscapeLeft() throws {
                XCUIApplication().launch()
                sleep(1)
                XCUIDevice.shared.orientation = .landscapeLeft
                sleep(1)
              }

              func testPortrait() throws {
                XCUIApplication().launch()
                sleep(1)
                XCUIDevice.shared.orientation = .portrait
                sleep(1)
              }
            }
            """
        ).strip()
        + "\n",
    )
    _write_if_changed(xcodeproj / "project.pbxproj", _PBXPROJ)
    _write_if_changed(xcodeproj / "xcshareddata" / "xcschemes" / "OrientationHarness.xcscheme", _XCSCHEME)
    return xcodeproj


def rotate_with_xctest(udid: str, landscape: bool) -> bool:
    """Set simulator orientation through XCTest without macOS Accessibility."""

    if shutil.which("xcodebuild") is None:
        _rlog("xcodebuild unavailable")
        return False

    project = _ensure_orientation_harness()
    test_name = "testLandscapeLeft" if landscape else "testPortrait"
    cmd = [
        "xcodebuild",
        "test",
        "-project",
        str(project),
        "-scheme",
        "OrientationHarness",
        "-destination",
        f"platform=iOS Simulator,id={udid}",
        f"-only-testing:OrientationHarnessUITests/OrientationHarnessUITests/{test_name}",
        "-quiet",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        _rlog(f"xctest rotate failed: {exc}")
        return False
    _rlog(f"xctest rotate rc={r.returncode} stderr={r.stderr.strip()!r}")
    return r.returncode == 0


_PBXPROJ = r"""// !$*UTF8*$!
{
	archiveVersion = 1;
	classes = {
	};
	objectVersion = 46;
	objects = {
		971B9400B8ED9441111D29FE /* App.swift in Sources */ = {isa = PBXBuildFile; fileRef = BBE6ADD0039AB09F359AEFA2 /* App.swift */; };
		C7AD59235CADB748BA1E35D6 /* OrientationHarnessUITests.swift in Sources */ = {isa = PBXBuildFile; fileRef = B9D424EE09C24726AE6BD5C2 /* OrientationHarnessUITests.swift */; };
		3224414FBDD00F8A5D76A527 /* OrientationHarnessUITests.xctest */ = {isa = PBXFileReference; explicitFileType = wrapper.cfbundle; includeInIndex = 0; path = OrientationHarnessUITests.xctest; sourceTree = BUILT_PRODUCTS_DIR; };
		9628938DC80962B31927CABE /* OrientationHarness.app */ = {isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = OrientationHarness.app; sourceTree = BUILT_PRODUCTS_DIR; };
		B9D424EE09C24726AE6BD5C2 /* OrientationHarnessUITests.swift */ = {isa = PBXFileReference; includeInIndex = 1; lastKnownFileType = sourcecode.swift; path = OrientationHarnessUITests.swift; sourceTree = "<group>"; };
		BBE6ADD0039AB09F359AEFA2 /* App.swift */ = {isa = PBXFileReference; includeInIndex = 1; lastKnownFileType = sourcecode.swift; path = App.swift; sourceTree = "<group>"; };
		1535DC16EFBB8FC9B51B6FA2 /* Frameworks */ = {isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; };
		531EB455E0D5CFFE76364533 /* Frameworks */ = {isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; };
		7BCB0322A4447DD3FBB1506D /* Products */ = {isa = PBXGroup; children = (9628938DC80962B31927CABE /* OrientationHarness.app */, 3224414FBDD00F8A5D76A527 /* OrientationHarnessUITests.xctest */); name = Products; sourceTree = "<group>"; };
		88914427F0133BE20774015C /* App */ = {isa = PBXGroup; children = (BBE6ADD0039AB09F359AEFA2 /* App.swift */); name = App; sourceTree = "<group>"; };
		EB4630432C515B66E8A10EEC /* UITests */ = {isa = PBXGroup; children = (B9D424EE09C24726AE6BD5C2 /* OrientationHarnessUITests.swift */); name = UITests; sourceTree = "<group>"; };
		F284ED264FADBC4EBA6ED5F4 = {isa = PBXGroup; children = (7BCB0322A4447DD3FBB1506D /* Products */, 88914427F0133BE20774015C /* App */, EB4630432C515B66E8A10EEC /* UITests */); sourceTree = "<group>"; };
		8A2F4152DA69FBDA9CC4EFE6 /* OrientationHarness */ = {isa = PBXNativeTarget; buildConfigurationList = 637BABDA1BB42B152A048308 /* Build configuration list for PBXNativeTarget "OrientationHarness" */; buildPhases = (70DD094E66C7702C1FFBF9AE /* Sources */, 1535DC16EFBB8FC9B51B6FA2 /* Frameworks */, F538A41A9C371A4274C471FE /* Resources */); buildRules = (); dependencies = (); name = OrientationHarness; productName = OrientationHarness; productReference = 9628938DC80962B31927CABE /* OrientationHarness.app */; productType = "com.apple.product-type.application"; };
		E257BFA0E752D07597980C62 /* OrientationHarnessUITests */ = {isa = PBXNativeTarget; buildConfigurationList = DF79604F9A99B5C25FC8391D /* Build configuration list for PBXNativeTarget "OrientationHarnessUITests" */; buildPhases = (969183BFD2E98697831D2870 /* Sources */, 531EB455E0D5CFFE76364533 /* Frameworks */, 702D0FC35FFB15BFB59171B5 /* Resources */); buildRules = (); dependencies = (E72734A01B2894108FCFB71D /* PBXTargetDependency */); name = OrientationHarnessUITests; productName = OrientationHarnessUITests; productReference = 3224414FBDD00F8A5D76A527 /* OrientationHarnessUITests.xctest */; productType = "com.apple.product-type.bundle.ui-testing"; };
		83971436AA2F6FA19D78E0A8 /* Project object */ = {isa = PBXProject; attributes = {LastSwiftUpdateCheck = 1600; LastUpgradeCheck = 1600;}; buildConfigurationList = C31B47211ACE6B14024EF390 /* Build configuration list for PBXProject "OrientationHarness" */; compatibilityVersion = "Xcode 3.2"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en, Base); mainGroup = F284ED264FADBC4EBA6ED5F4; minimizedProjectReferenceProxies = 0; preferredProjectObjectVersion = 77; productRefGroup = 7BCB0322A4447DD3FBB1506D /* Products */; projectDirPath = ""; projectRoot = ""; targets = (8A2F4152DA69FBDA9CC4EFE6 /* OrientationHarness */, E257BFA0E752D07597980C62 /* OrientationHarnessUITests */); };
		702D0FC35FFB15BFB59171B5 /* Resources */ = {isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; };
		F538A41A9C371A4274C471FE /* Resources */ = {isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; };
		70DD094E66C7702C1FFBF9AE /* Sources */ = {isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = (971B9400B8ED9441111D29FE /* App.swift in Sources */); runOnlyForDeploymentPostprocessing = 0; };
		969183BFD2E98697831D2870 /* Sources */ = {isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = (C7AD59235CADB748BA1E35D6 /* OrientationHarnessUITests.swift in Sources */); runOnlyForDeploymentPostprocessing = 0; };
		E72734A01B2894108FCFB71D /* PBXTargetDependency */ = {isa = PBXTargetDependency; target = 8A2F4152DA69FBDA9CC4EFE6 /* OrientationHarness */; };
		5E19FB7BA84A6E38983F5B2B /* Debug */ = {isa = XCBuildConfiguration; buildSettings = {CLANG_ENABLE_OBJC_WEAK = NO; CODE_SIGNING_ALLOWED = NO; GENERATE_INFOPLIST_FILE = YES; INFOPLIST_KEY_UISupportedInterfaceOrientations = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight UIInterfaceOrientationPortraitUpsideDown"; "INFOPLIST_KEY_UISupportedInterfaceOrientations~ipad" = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight UIInterfaceOrientationPortraitUpsideDown"; IPHONEOS_DEPLOYMENT_TARGET = 17.0; LD_RUNPATH_SEARCH_PATHS = "$(inherited) @executable_path/Frameworks"; PRODUCT_BUNDLE_IDENTIFIER = "dev.simmer.orientation-harness"; SDKROOT = iphoneos; SWIFT_VERSION = 5.0; TARGETED_DEVICE_FAMILY = "1,2";}; name = Debug; };
		C34EA995AB2915919A6170DF /* Release */ = {isa = XCBuildConfiguration; buildSettings = {CLANG_ENABLE_OBJC_WEAK = NO; CODE_SIGNING_ALLOWED = NO; GENERATE_INFOPLIST_FILE = YES; INFOPLIST_KEY_UISupportedInterfaceOrientations = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight UIInterfaceOrientationPortraitUpsideDown"; "INFOPLIST_KEY_UISupportedInterfaceOrientations~ipad" = "UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight UIInterfaceOrientationPortraitUpsideDown"; IPHONEOS_DEPLOYMENT_TARGET = 17.0; LD_RUNPATH_SEARCH_PATHS = "$(inherited) @executable_path/Frameworks"; PRODUCT_BUNDLE_IDENTIFIER = "dev.simmer.orientation-harness"; SDKROOT = iphoneos; SWIFT_VERSION = 5.0; TARGETED_DEVICE_FAMILY = "1,2"; VALIDATE_PRODUCT = YES;}; name = Release; };
		7D8188F176E439220C30CE05 /* Debug */ = {isa = XCBuildConfiguration; buildSettings = {ALWAYS_SEARCH_USER_PATHS = NO; CLANG_ENABLE_MODULES = YES; CODE_SIGNING_ALLOWED = NO; DEBUG_INFORMATION_FORMAT = dwarf; ENABLE_TESTABILITY = YES; GENERATE_INFOPLIST_FILE = YES; IPHONEOS_DEPLOYMENT_TARGET = 17.0; PRODUCT_NAME = "$(TARGET_NAME)"; SDKROOT = iphoneos; SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG; SWIFT_OPTIMIZATION_LEVEL = "-Onone"; SWIFT_VERSION = 5.0;}; name = Debug; };
		93362937DC239E2E8504C0BC /* Release */ = {isa = XCBuildConfiguration; buildSettings = {ALWAYS_SEARCH_USER_PATHS = NO; CLANG_ENABLE_MODULES = YES; CODE_SIGNING_ALLOWED = NO; DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym"; GENERATE_INFOPLIST_FILE = YES; IPHONEOS_DEPLOYMENT_TARGET = 17.0; PRODUCT_NAME = "$(TARGET_NAME)"; SDKROOT = iphoneos; SWIFT_COMPILATION_MODE = wholemodule; SWIFT_OPTIMIZATION_LEVEL = "-O"; SWIFT_VERSION = 5.0;}; name = Release; };
		97ABD56471B1F34A090B5E33 /* Debug */ = {isa = XCBuildConfiguration; buildSettings = {CLANG_ENABLE_OBJC_WEAK = NO; CODE_SIGNING_ALLOWED = NO; GENERATE_INFOPLIST_FILE = YES; IPHONEOS_DEPLOYMENT_TARGET = 17.0; PRODUCT_BUNDLE_IDENTIFIER = "dev.simmer.orientation-harness.uitests"; SDKROOT = iphoneos; SWIFT_VERSION = 5.0; TEST_TARGET_NAME = OrientationHarness;}; name = Debug; };
		B9DCE88DDE8D44375DC714EB /* Release */ = {isa = XCBuildConfiguration; buildSettings = {CLANG_ENABLE_OBJC_WEAK = NO; CODE_SIGNING_ALLOWED = NO; GENERATE_INFOPLIST_FILE = YES; IPHONEOS_DEPLOYMENT_TARGET = 17.0; PRODUCT_BUNDLE_IDENTIFIER = "dev.simmer.orientation-harness.uitests"; SDKROOT = iphoneos; SWIFT_VERSION = 5.0; TEST_TARGET_NAME = OrientationHarness; VALIDATE_PRODUCT = YES;}; name = Release; };
		637BABDA1BB42B152A048308 /* Build configuration list for PBXNativeTarget "OrientationHarness" */ = {isa = XCConfigurationList; buildConfigurations = (C34EA995AB2915919A6170DF /* Release */, 5E19FB7BA84A6E38983F5B2B /* Debug */); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; };
		C31B47211ACE6B14024EF390 /* Build configuration list for PBXProject "OrientationHarness" */ = {isa = XCConfigurationList; buildConfigurations = (7D8188F176E439220C30CE05 /* Debug */, 93362937DC239E2E8504C0BC /* Release */); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; };
		DF79604F9A99B5C25FC8391D /* Build configuration list for PBXNativeTarget "OrientationHarnessUITests" */ = {isa = XCConfigurationList; buildConfigurations = (B9DCE88DDE8D44375DC714EB /* Release */, 97ABD56471B1F34A090B5E33 /* Debug */); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; };
	};
	rootObject = 83971436AA2F6FA19D78E0A8 /* Project object */;
}
"""


_XCSCHEME = r"""<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.3">
   <BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES">
      <BuildActionEntries>
         <BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="8A2F4152DA69FBDA9CC4EFE6" BuildableName="OrientationHarness.app" BlueprintName="OrientationHarness" ReferencedContainer="container:OrientationHarness.xcodeproj"></BuildableReference></BuildActionEntry>
         <BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="E257BFA0E752D07597980C62" BuildableName="OrientationHarnessUITests.xctest" BlueprintName="OrientationHarnessUITests" ReferencedContainer="container:OrientationHarness.xcodeproj"></BuildableReference></BuildActionEntry>
      </BuildActionEntries>
   </BuildAction>
   <TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.DebuggerFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="YES">
      <MacroExpansion><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="8A2F4152DA69FBDA9CC4EFE6" BuildableName="OrientationHarness.app" BlueprintName="OrientationHarness" ReferencedContainer="container:OrientationHarness.xcodeproj"></BuildableReference></MacroExpansion>
      <Testables><TestableReference skipped="NO"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="E257BFA0E752D07597980C62" BuildableName="OrientationHarnessUITests.xctest" BlueprintName="OrientationHarnessUITests" ReferencedContainer="container:OrientationHarness.xcodeproj"></BuildableReference></TestableReference></Testables>
   </TestAction>
   <LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.DebuggerFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="YES">
      <BuildableProductRunnable runnableDebuggingMode="0"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="8A2F4152DA69FBDA9CC4EFE6" BuildableName="OrientationHarness.app" BlueprintName="OrientationHarness" ReferencedContainer="container:OrientationHarness.xcodeproj"></BuildableReference></BuildableProductRunnable>
   </LaunchAction>
   <ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"></ProfileAction>
   <AnalyzeAction buildConfiguration="Debug"></AnalyzeAction>
   <ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"></ArchiveAction>
</Scheme>
"""
