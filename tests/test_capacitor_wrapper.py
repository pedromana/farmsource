import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_capacitor_config_targets_existing_farmsource_web_app() -> None:
    config = (ROOT / "capacitor.config.ts").read_text()
    assert 'appId: "com.farmsource.shop"' in config
    assert 'appName: "Farmsource Shop"' in config
    assert 'appId: "com.farmsource.driver"' in config
    assert 'appName: "Farmsource Driver"' in config
    assert 'webDir: "app/static"' in config
    assert "FARMSOURCE_APP_MODE" in config
    assert "FARMSOURCE_MOBILE_SERVER_URL" in config
    assert "/customer/catalog" in config
    assert "/driver" in config


def test_android_wrapper_project_is_configured() -> None:
    android_config = json.loads((ROOT / "android" / "app" / "src" / "main" / "assets" / "capacitor.config.json").read_text())
    strings = (ROOT / "android" / "app" / "src" / "main" / "res" / "values" / "strings.xml").read_text()
    manifest = (ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text()
    assert android_config["appId"] in {"com.farmsource.shop", "com.farmsource.driver", "com.farmsource.app"}
    assert android_config["appName"] in {"Farmsource Shop", "Farmsource Driver", "Farmsource"}
    assert android_config["webDir"] == "app/static"
    assert "Farmsource" in strings
    assert any(app_id in strings for app_id in ("com.farmsource.shop", "com.farmsource.driver", "com.farmsource.app"))
    assert 'android.permission.INTERNET' in manifest


def test_ios_wrapper_project_is_configured() -> None:
    ios_config = json.loads((ROOT / "ios" / "App" / "App" / "capacitor.config.json").read_text())
    info_plist = (ROOT / "ios" / "App" / "App" / "Info.plist").read_text()
    assert ios_config["appId"] in {"com.farmsource.shop", "com.farmsource.driver", "com.farmsource.app"}
    assert ios_config["appName"] in {"Farmsource Shop", "Farmsource Driver", "Farmsource"}
    assert ios_config["webDir"] == "app/static"
    assert "CFBundleDisplayName" in info_plist


def test_wrapper_assets_and_docs_exist() -> None:
    assert (ROOT / "app" / "static" / "icons" / "icon.svg").exists()
    assert (ROOT / "app" / "static" / "icons" / "splash.svg").exists()
    assert (ROOT / "android" / "app" / "src" / "main" / "res" / "drawable-v24" / "ic_launcher_foreground.xml").exists()
    assert (ROOT / "ios" / "App" / "App" / "Assets.xcassets" / "AppIcon.appiconset" / "Contents.json").exists()
    readme = (ROOT / "README.md").read_text()
    assert "Mobile App Wrapper" in readme
    assert "Farmsource Shop" in readme
    assert "Farmsource Driver" in readme
    assert "iOS builds require macOS and Xcode" in readme
