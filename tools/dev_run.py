"""開發用：不經 MFAAvalonia，直接連雷電模擬器執行「讀取家族成員」。

用法：python tools/dev_run.py
需要：模擬器已開啟並停在家族「成員」分頁、`.env` 已填寫、已下載 OCR 模型。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from maa.controller import AdbController  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402
from maa.toolkit import Toolkit  # noqa: E402

from actions import ReadMembers  # noqa: E402


def main() -> int:
    Toolkit.init_option(str(ROOT / "debug"))
    devices = Toolkit.find_adb_devices()
    if not devices:
        print("找不到模擬器。請先開啟雷電模擬器（必要時以系統管理員身分執行）。")
        return 1
    dev = devices[0]
    print(f"連線：{dev.name} {dev.address}")
    ctrl = AdbController(
        adb_path=dev.adb_path,
        address=dev.address,
        screencap_methods=dev.screencap_methods,
        input_methods=dev.input_methods,
        config=dev.config,
    )
    ctrl.set_screenshot_use_raw_size(True)  # 與 interface 的 display_raw 相同：1920×1080
    ctrl.post_connection().wait()
    res = Resource()
    res.post_bundle(str(ROOT / "assets" / "resource")).wait()
    res.register_custom_action("ReadMembers", ReadMembers())
    tasker = Tasker()
    tasker.bind(res, ctrl)
    if not tasker.inited:
        print("MaaFramework 初始化失敗。")
        return 1
    detail = tasker.post_task("ReadMembers").wait().get()
    return 0 if detail and detail.status.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
