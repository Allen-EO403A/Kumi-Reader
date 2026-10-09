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

"""開發用：從指定的模擬器截一張原始解析度的圖到 debug/snap.png（只截圖，不點擊）。

用法：python tools/snap.py [模擬器名稱或位址的一部分，例如 A1]
"""
from __future__ import annotations

import sys
from pathlib import Path

from maa.controller import AdbController
from maa.toolkit import Toolkit
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    Toolkit.init_option(str(ROOT / "debug"))
    devices = Toolkit.find_adb_devices()
    for d in devices:
        print(f"找到模擬器：{d.name}（{d.address}）")
    wanted = sys.argv[1] if len(sys.argv) > 1 else None
    matches = [d for d in devices if not wanted or wanted in d.name or wanted in d.address]
    if not matches:
        print("找不到指定的模擬器。")
        return 1
    d = matches[0]
    ctrl = AdbController(
        adb_path=d.adb_path, address=d.address,
        screencap_methods=d.screencap_methods, input_methods=d.input_methods, config=d.config,
    )
    ctrl.set_screenshot_use_raw_size(True)
    ctrl.post_connection().wait()
    image = ctrl.post_screencap().wait().get()
    out = ROOT / "debug" / "snap.png"
    out.parent.mkdir(exist_ok=True)
    Image.fromarray(image[:, :, ::-1]).save(out)
    print(f"已截圖：{d.name} {image.shape[1]}×{image.shape[0]} → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
