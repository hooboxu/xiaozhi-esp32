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

    # 深度清理步骤
    if os.path.exists("build"):
        print("清理旧的编译目录 (build)...")
        shutil.rmtree("build")
    if os.path.exists("sdkconfig"):
        print("移除旧的配置 (sdkconfig)...")
        os.remove("sdkconfig")

    # 1. 准备环境 (修复此处缩进)
    os.environ.pop("IDF_TARGET", None)
    if os.system(f"idf.py set-target {target}") != 0:
        print("❌ set-target 失败")
        sys.exit(1)

    # 2. 注入配置
    sdkconfig_lines = [f"CONFIG_BOARD_TYPE_WAVESHARE_S3_RLCD_4_2=y"]
    sdkconfig_lines.extend(build_cfg.get("sdkconfig_append", []))
    
    # 强制补全 PSRAM 八线配置 (针对 N16R8 模组)
    psram_fixes = ["CONFIG_SPIRAM_MODE_OCT=y", "CONFIG_SPIRAM_TYPE_AUTO=y"]
    for fix in psram_fixes:
        if fix not in sdkconfig_lines:
            sdkconfig_lines.append(fix)

    final_configs = _apply_auto_selects(sdkconfig_lines)

    with Path("sdkconfig").open("a") as f:
        f.write("\n# Final Release Configs\n")
        for line in final_configs:
            f.write(f"{line}\n")

    # 3. 执行编译
    build_cmd = f"idf.py -DBOARD_NAME={name} -DBOARD_TYPE={board_type} build"
    if os.system(build_cmd) != 0:
        print("❌ 编译失败")
        sys.exit(1)

    # 4. 合并与打包
    if os.system("idf.py merge-bin") != 0:
        print("❌ 合并 bin 失败")
        sys.exit(1)

    out_dir = Path("releases")
    out_dir.mkdir(exist_ok=True)
    zip_path = out_dir / f"v{project_version}_{name}.zip"
    
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        zipf.write("build/merged-binary.bin", arcname="merged-binary.bin")
    
    print(f"\n✅ 编译成功！固件已打包至: {zip_path}")

if __name__ == "__main__":
    do_compile_waveshare()
