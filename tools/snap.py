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
