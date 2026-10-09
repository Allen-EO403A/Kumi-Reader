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

"""開發用：量測成員列表的滑動距離（只滑動與截圖，不點擊任何東西）。

用法：python tools/scroll_probe.py A1
1. 先滑到名單最上面。
2. 以「按住滑動、停住再放開」的方式往下滑，每次記下各列的貢獻度與位置，算出實際移動了幾列。
3. 一路滑到底，輸出完整名單（暱稱、職位、貢獻度）到 debug/roster.txt。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "tools"))

from maa.controller import AdbController  # noqa: E402
from maa.toolkit import Toolkit  # noqa: E402

import members_flow as F  # noqa: E402
from check_samples import Ocr  # noqa: E402
from kumi_reader.device import region_changed  # noqa: E402
from kumi_reader.text import parse_int  # noqa: E402


def connect(wanted: str | None) -> AdbController:
    Toolkit.init_option(str(ROOT / "debug"))
    devices = [d for d in Toolkit.find_adb_devices() if not wanted or wanted in d.name or wanted in d.address]
    d = devices[0]
    ctrl = AdbController(
        adb_path=d.adb_path, address=d.address,
        screencap_methods=d.screencap_methods, input_methods=d.input_methods, config=d.config,
    )
    ctrl.set_screenshot_use_raw_size(True)
    ctrl.post_connection().wait()
    print(f"連線：{d.name}")
    return ctrl


def drag(ctrl: AdbController, x: int, y1: int, y2: int, steps: int = 12, hold: float = 0.4) -> None:
    """按下 → 分段移動 → 停住 hold 秒 → 放開（停住可以消掉慣性）。"""
    ctrl.post_touch_down(x, y1).wait()
    for i in range(1, steps + 1):
        ctrl.post_touch_move(x, round(y1 + (y2 - y1) * i / steps)).wait()
        time.sleep(0.02)
    time.sleep(hold)
    ctrl.post_touch_up().wait()


def rows(ctrl: AdbController, ocr: Ocr):
    image = ctrl.post_screencap().wait().get()
    out = []
    for top in F.find_row_tops(image):
        contribution = parse_int(ocr(image, F.row_contribution_roi(top)))
        if contribution is None:
            continue
        out.append((top, ocr(image, F.row_name_roi(top)), ocr(image, F.row_role_roi(top)), contribution))
    return image, out


def main() -> int:
    ctrl = connect(sys.argv[1] if len(sys.argv) > 1 else None)
    ocr = Ocr()
    # 回到最上面
    for _ in range(40):
        before = ctrl.post_screencap().wait().get()
        drag(ctrl, 1150, 420, 950, hold=0.1)
        time.sleep(0.6)
        if not region_changed(before, ctrl.post_screencap().wait().get(), F.LIST_REGION):
            break
    roster: list[tuple[str, str, int]] = []
    seen: set[int] = set()
    image, current = rows(ctrl, ocr)
    for page in range(60):
        for top, name, role, contribution in current:
            if contribution not in seen:
                seen.add(contribution)
                roster.append((name, role, contribution))
        prev = {c: top for top, _, _, c in current}
        before = image
        drag(ctrl, 1150, 900, 560)  # 340 px ≈ 3 列
        time.sleep(0.6)
        image, current = rows(ctrl, ocr)
        moved = [prev[c] - top for top, _, _, c in current if c in prev]
        overlap = len(moved)
        print(f"第 {page + 1} 次滑動：重疊 {overlap} 列，位移 {sorted(set(moved))} px")
        if not region_changed(before, image, F.LIST_REGION):
            print("已到底")
            break
    out = ROOT / "debug" / "roster.txt"
    out.write_text("\n".join(f"{i + 1}\t{n}\t{r}\t{c}" for i, (n, r, c) in enumerate(roster)), encoding="utf-8")
    print(f"名單共 {len(roster)} 人 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
