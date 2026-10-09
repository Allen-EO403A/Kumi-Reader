# Kumi Reader - 讀取「忍者必須死3」家族成員與深淵排行並上傳到 Kumi
# Copyright (C) 2026 Allen <allen@umail.tw>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""開發用：不經 MFAAvalonia，直接連雷電模擬器執行讀取任務。

用法：python tools/dev_run.py [模擬器名稱或位址的一部分，例如 A1] [--missing | --abyss | --upload]
預設「讀取家族成員」；--missing 為「補讀缺少的成員」；--abyss 為「讀取深淵排行」；--upload 為「上傳讀取結果」。
不帶參數時列出所有模擬器並連第一台。
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

from abyss_runner import ReadAbyssAction  # noqa: E402  不載入 actions（AgentServer）
from members_runner import ReadMembersAction, ReadMissingMembersAction  # noqa: E402
from upload_runner import UploadAction  # noqa: E402


def main() -> int:
    Toolkit.init_option(str(ROOT / "debug"))
    devices = Toolkit.find_adb_devices()
    if not devices:
        print("找不到模擬器。請先開啟雷電模擬器（必要時以系統管理員身分執行）。")
        return 1
    for d in devices:
        print(f"找到模擬器：{d.name}（{d.address}）")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    wanted = args[0] if args else None
    matches = [d for d in devices if not wanted or wanted in d.name or wanted in d.address]
    if not matches:
        print(f"找不到名稱或位址包含「{wanted}」的模擬器。")
        return 1
    dev = matches[0]
    print(f"連線：{dev.name}（{dev.address}）")
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
    res.register_custom_action("ReadMembers", ReadMembersAction())
    res.register_custom_action("ReadMissingMembers", ReadMissingMembersAction())
    res.register_custom_action("Upload", UploadAction())
    res.register_custom_action("ReadAbyss", ReadAbyssAction())
    tasker = Tasker()
    tasker.bind(res, ctrl)
    if not tasker.inited:
        print("MaaFramework 初始化失敗。")
        return 1
    flags = {"--missing": "ReadMissingMembers", "--abyss": "ReadAbyss", "--upload": "Upload"}
    entry = next((e for f, e in flags.items() if f in sys.argv), "ReadMembers")
    detail = tasker.post_task(entry).wait().get()
    return 0 if detail and detail.status.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
