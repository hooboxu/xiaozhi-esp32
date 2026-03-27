import sys
import os
import json
import zipfile
import shutil
from pathlib import Path
from typing import Optional

# 自动切换到项目根目录
os.chdir(Path(__file__).resolve().parent.parent)

_BOARDS_DIR = Path("main/boards")

# 自动选择规则：补全蓝牙/WiFi等依赖项
_AUTO_SELECT_RULES: dict[str, list[str]] = {
    "CONFIG_USE_ESP_BLUFI_WIFI_PROVISIONING": [
        "CONFIG_BT_ENABLED=y",
        "CONFIG_BT_BLUEDROID_ENABLED=y",
        "CONFIG_BT_BLE_42_FEATURES_SUPPORTED=y",
        "CONFIG_BT_BLE_50_FEATURES_SUPPORTED=n",
        "CONFIG_BT_BLE_BLUFI_ENABLE=y",
        "CONFIG_MBEDTLS_DHM_C=y",
    ],
}

def get_project_version() -> str:
    try:
        with Path("CMakeLists.txt").open() as f:
            for line in f:
                if "set(PROJECT_VER" in line:
                    return line.split("\"")[1]
    except:
        return "1.0.0"
    return "1.0.0"

def _apply_auto_selects(sdkconfig_append: list[str]) -> list[str]:
    items = list(sdkconfig_append)
    existing_keys = {entry.split("=", 1)[0] for entry in items}
    for key, deps in _AUTO_SELECT_RULES.items():
        for entry in sdkconfig_append:
            if entry.startswith(f"{key}=y"):
                for dep in deps:
                    dep_key = dep.split("=", 1)[0]
                    if dep_key not in existing_keys:
                        items.append(dep)
                        existing_keys.add(dep_key)
                break
    return items

def do_compile_waveshare():
    """专为 Waveshare-s3-rlcd-4.2 定制的编译流程"""
    board_type = "waveshare-s3-rlcd-4.2"
    cfg_path = _BOARDS_DIR / board_type / "config.json"
    
    if not cfg_path.exists():
        print(f"[ERROR] 找不到配置文件: {cfg_path}")
        sys.exit(1)

    with cfg_path.open() as f:
        cfg = json.load(f)
    
    build_cfg = cfg["builds"][0] 
    target = cfg["target"]
    name = build_cfg["name"]
    project_version = get_project_version()

    print(f"\n🚀 开始编译专用固件: {name} (Target: {target})")
    print("="*50)

    # --- 深度清理步骤：解决 component_requirements.py 报错 ---
    if os.path.exists("build"):
        print("清理旧的编译目录 (build)...")
        shutil.rmtree("build")
    if os.path.exists("sdkconfig"):
        print("移除旧的配置 (sdkconfig)...")
        os.remove("sdkconfig")
    # -----------------------------------------------------

    # 1. 准备环境
    os.environ.pop("IDF_TARGET", None)
    if os.system(f"idf.py set-target {target}") != 0:
