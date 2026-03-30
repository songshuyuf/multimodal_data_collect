"""
一键构建脚本 — PyInstaller 打包 + Inno Setup 安装包
===================================================
用法:
    python build.py              # 完整构建（PyInstaller + Inno Setup）
    python build.py --skip-inno  # 仅 PyInstaller 打包
    python build.py --upload     # 构建后上传到服务器
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from version import APP_VERSION, APP_NAME, APP_ID


def banner(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def ensure_ico():
    """确保 assets/logo.ico 存在，不存在则从 .png 转换。"""
    ico_path = os.path.join(PROJECT_ROOT, "assets", "logo.ico")
    png_path = os.path.join(PROJECT_ROOT, "assets", "logo.png")

    if os.path.isfile(ico_path):
        print(f"[OK] icon exists: {ico_path}")
        return

    if not os.path.isfile(png_path):
        print("[!!] assets/logo.png not found, skip icon generation")
        return

    try:
        from PIL import Image
        img = Image.open(png_path)
        img.save(ico_path, format="ICO",
                 sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print(f"[OK] icon generated: {ico_path}")
    except ImportError:
        print("[!!] Pillow required: pip install Pillow")
        sys.exit(1)


def clean_dist():
    """清理旧的构建产物。"""
    for d in ["build", "dist"]:
        path = os.path.join(PROJECT_ROOT, d)
        if os.path.isdir(path):
            shutil.rmtree(path)
            print(f"[OK] cleaned: {path}")


def run_pyinstaller():
    """执行 PyInstaller 构建。"""
    banner("PyInstaller 打包")

    spec_file = os.path.join(PROJECT_ROOT, "build.spec")
    if not os.path.isfile(spec_file):
        print("[FAIL] build.spec not found")
        sys.exit(1)

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", spec_file]
    print(f"执行: {' '.join(cmd)}\n")

    t0 = time.time()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"\n[FAIL] PyInstaller build failed (exit code {result.returncode})")
        sys.exit(1)

    dist_dir = os.path.join(PROJECT_ROOT, "dist", APP_ID)
    if not os.path.isdir(dist_dir):
        print(f"[FAIL] dist dir not found: {dist_dir}")
        sys.exit(1)

    total_size = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, fns in os.walk(dist_dir) for f in fns
    )
    print(f"\n[OK] PyInstaller build succeeded")
    print(f"    Output: {dist_dir}")
    print(f"    Size:   {total_size / (1024*1024):.1f} MB")
    print(f"    Time:   {elapsed:.1f}s")


def run_inno_setup():
    """执行 Inno Setup 编译。"""
    banner("Inno Setup 打包")

    iss_file = os.path.join(PROJECT_ROOT, "installer.iss")
    if not os.path.isfile(iss_file):
        print("[FAIL] installer.iss not found")
        sys.exit(1)

    iscc_candidates = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        "ISCC",
    ]
    iscc = None
    for candidate in iscc_candidates:
        if os.path.isfile(candidate) or shutil.which(candidate):
            iscc = candidate
            break

    if iscc is None:
        print("[FAIL] Inno Setup compiler (ISCC.exe) not found")
        print("    Install Inno Setup 6: https://jrsoftware.org/isdl.php")
        print("    Or add ISCC.exe to PATH")
        return False

    output_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(output_dir, exist_ok=True)

    cmd = [iscc, iss_file]
    print(f"执行: {' '.join(cmd)}\n")

    t0 = time.time()
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"\n[FAIL] Inno Setup build failed (exit code {result.returncode})")
        return False

    expected_output = os.path.join(output_dir, f"AiArtTreat_Setup_v{APP_VERSION}.exe")
    if os.path.isfile(expected_output):
        size = os.path.getsize(expected_output)
        md5 = hashlib.md5(open(expected_output, "rb").read()).hexdigest()
        print(f"\n[OK] Installer created successfully")
        print(f"    File: {expected_output}")
        print(f"    Size: {size / (1024*1024):.1f} MB")
        print(f"    MD5:  {md5}")
        print(f"    Time: {elapsed:.1f}s")
    else:
        print(f"[!!] Installer not found: {expected_output}")

    return True


def upload_to_server(server_url: str, api_key: str):
    """将安装包上传到服务器并注册新版本。"""
    banner("上传到服务器")

    import requests

    installer_path = os.path.join(
        PROJECT_ROOT, "output", f"AiArtTreat_Setup_v{APP_VERSION}.exe"
    )
    if not os.path.isfile(installer_path):
        print(f"[FAIL] Installer not found: {installer_path}")
        return False

    url = f"{server_url.rstrip('/')}/api/v1/update/release"
    print(f"上传到: {url}")
    print(f"文件: {installer_path}")
    print(f"版本: {APP_VERSION}")

    size_mb = os.path.getsize(installer_path) / (1024 * 1024)
    print(f"大小: {size_mb:.1f} MB\n")

    with open(installer_path, "rb") as f:
        files = {"installer": (os.path.basename(installer_path), f, "application/octet-stream")}
        data = {
            "version": APP_VERSION,
            "platform": "windows",
            "release_notes": f"v{APP_VERSION} 版本更新",
            "mandatory": "false",
        }
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            resp = requests.post(url, files=files, data=data, headers=headers, timeout=600)
            if resp.status_code == 200:
                print(f"[OK] Upload succeeded: {resp.json()}")
                return True
            else:
                print(f"[FAIL] Upload failed ({resp.status_code}): {resp.text}")
                return False
        except Exception as e:
            print(f"[FAIL] Upload error: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description=f"构建 {APP_NAME} v{APP_VERSION}")
    parser.add_argument("--skip-inno", action="store_true", help="跳过 Inno Setup 打包")
    parser.add_argument("--skip-pyinstaller", action="store_true", help="跳过 PyInstaller（仅重新打包安装包）")
    parser.add_argument("--no-clean", action="store_true", help="不清理旧构建产物")
    parser.add_argument("--upload", action="store_true", help="构建后上传到服务器")
    parser.add_argument("--server", default="http://172.16.55.196:8000", help="服务器地址")
    parser.add_argument("--api-key", default="", help="API Key（上传用）")
    args = parser.parse_args()

    banner(f"构建 {APP_NAME} v{APP_VERSION}")

    ensure_ico()

    if not args.no_clean and not args.skip_pyinstaller:
        clean_dist()

    if not args.skip_pyinstaller:
        run_pyinstaller()

    if not args.skip_inno:
        run_inno_setup()

    if args.upload:
        if not args.api_key:
            print("[!!] --api-key is required for upload")
        else:
            upload_to_server(args.server, args.api_key)

    banner("构建完成")
    print(f"版本:  {APP_VERSION}")
    print(f"输出:  dist/{APP_ID}/")
    if not args.skip_inno:
        print(f"安装包: output/AiArtTreat_Setup_v{APP_VERSION}.exe")
    print()


if __name__ == "__main__":
    main()
