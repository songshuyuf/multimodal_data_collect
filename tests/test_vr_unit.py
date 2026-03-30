"""
VR ADB 单元测试
================
测试 PC 通过 Wi-Fi ADB 控制 PICO 4 播放本地视频目录。

用法：
  python -X utf8 tests/test_vr_unit.py --pico-ip 172.20.10.6
  python -X utf8 tests/test_vr_unit.py --pico-ip 172.20.10.6 --list
  python -X utf8 tests/test_vr_unit.py --pico-ip 172.20.10.6 --play-all
  python -X utf8 tests/test_vr_unit.py --pico-ip 172.20.10.6 --play hangyi.mp4
"""

import argparse
import sys
import time
import os

_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

from devices.vr_sync import VRADBController, DEFAULT_PICO_DIR


def main():
    ap = argparse.ArgumentParser(description="VR ADB 单元测试")
    ap.add_argument("--pico-ip",     default="",                  help="PICO 的局域网 IP（WiFi 模式）")
    ap.add_argument("--pico-port",   type=int, default=5555,      help="ADB 端口（默认 5555）")
    ap.add_argument("--serial",      default="PA8210MGH3300381G", help="PICO USB 序列号（USB 模式，优先）")
    ap.add_argument("--pico-dir",  default=DEFAULT_PICO_DIR, help="PICO 上的视频目录")
    ap.add_argument("--list",      action="store_true",     help="列出目录内所有视频")
    ap.add_argument("--play-all",  action="store_true",     help="依次播放目录内所有视频")
    ap.add_argument("--play",      metavar="FILE",          help="播放指定文件名（如 hangyi.mp4）")
    ap.add_argument("--secs",      type=int, default=30,    help="每个视频播放秒数（默认 30 秒）")
    ap.add_argument("--adb",       default=None,            help="adb 可执行文件路径（默认自动查找）")
    args = ap.parse_args()

    # adb 路径：优先用参数指定，其次项目内，最后系统 PATH
    import sys as _sys
    adb_cmd = args.adb
    if not adb_cmd:
        _local = os.path.join(_root, "vr", "platform-tools",
                              "adb.exe" if _sys.platform == "win32" else "adb")
        adb_cmd = _local if os.path.exists(_local) else "adb"

    vr = VRADBController(
        pico_ip=args.pico_ip,
        pico_port=args.pico_port,
        pico_serial=args.serial,
        pico_video_dir=args.pico_dir,
        adb_cmd=adb_cmd,
    )
    mode = f"USB ({args.serial})" if args.serial else f"WiFi ({args.pico_ip})"
    print(f"  模式 : {mode}")
    print(f"  ADB  : {adb_cmd}")

    print("=" * 50)
    print("VR ADB 单元测试")
    print(f"  PICO : {args.pico_ip}:{args.pico_port}")
    print(f"  目录 : {args.pico_dir}")
    print("=" * 50)

    try:
        # 连接
        print("\n[1] 连接 PICO...")
        ok = vr.connect()
        assert ok, "连接失败，请检查 PICO IP 和 ADB"
        print("    [OK] 连接成功")

        # 列出视频
        videos = vr.list_videos_on_pico()
        print(f"\n[2] 目录内视频（共 {len(videos)} 个）：")
        if videos:
            for f in videos:
                print(f"    - {f}")
        else:
            print("    (空目录或路径不存在)")

        # 播放指定文件
        if args.play:
            print(f"\n[3] 播放 {args.play}（{args.secs} 秒后停止）...")
            ok = vr.play(args.play)
            assert ok, "启动视频失败"
            print(f"    [OK] 视频已启动，等待 {args.secs} 秒...")
            time.sleep(args.secs)
            vr.stop()
            print("    [OK] 视频已停止")

        # 依次播放全部
        elif args.play_all:
            assert videos, "目录内没有视频，无法播放"
            print(f"\n[3] 依次播放全部 {len(videos)} 个视频（每个 {args.secs} 秒）...")
            print("    提示：按 Ctrl+C 可提前停止\n")
            try:
                vr.play_all(interval=args.secs)
            except KeyboardInterrupt:
                vr.stop()
                print("\n    [中断] 已停止")

        print("\n[PASS] 全部通过\n")

    except AssertionError as e:
        print(f"\n[FAIL] {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)
    finally:
        vr.disconnect()


if __name__ == "__main__":
    main()
