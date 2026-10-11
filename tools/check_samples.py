# Kumi Reader - 讀取「忍者必須死」家族成員與深淵排行並上傳到 Kumi
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

"""用 MaaFramework 的 OCR 離線辨識截圖中的固定區域，列出結果供人工比對。

用法：
  python tools/check_samples.py list samples/member-list.png      # 成員列表：每一列的暱稱、職位、貢獻度
  python tools/check_samples.py profile samples/profile-*.png     # 個人資訊頁：暱稱與 UID
需要先執行 tools/download_ocr_model.py。
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from maa.controller import CustomController  # noqa: E402
from maa.pipeline import JOCR, JRecognitionType  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402
from maa.toolkit import Toolkit  # noqa: E402

import members_flow as F  # noqa: E402
from kumi_reader.text import parse_member_count, parse_name, parse_role, parse_uid  # noqa: E402
from kumi_reader.uid_digits import read_uid  # noqa: E402


class StillController(CustomController):
    """離線用：不連模擬器，辨識時直接給圖。"""

    def connect(self): return True
    def connected(self): return True
    def request_uuid(self): return "offline"
    def get_features(self): return 0
    def start_app(self, intent): return True
    def stop_app(self, intent): return True
    def screencap(self): return np.zeros((1080, 1920, 3), dtype=np.uint8)
    def click(self, x, y): return True
    def swipe(self, x1, y1, x2, y2, duration): return True
    def touch_down(self, contact, x, y, pressure): return True
    def touch_move(self, contact, x, y, pressure): return True
    def touch_up(self, contact): return True
    def click_key(self, keycode): return True
    def input_text(self, text): return True
    def key_down(self, keycode): return True
    def key_up(self, keycode): return True
    def scroll(self, dx, dy): return True
    def relative_move(self, dx, dy): return True
    def shell(self, cmd, timeout): return ""
    def inactive(self): return True
    def get_custom_info(self): return "{}"


class Ocr:
    def __init__(self):
        Toolkit.init_option(str(ROOT / "debug"))
        self.ctrl = StillController()
        self.ctrl.post_connection().wait()
        self.res = Resource()
        self.res.post_bundle(str(ROOT / "assets" / "resource")).wait()
        self.tasker = Tasker()
        self.tasker.bind(self.res, self.ctrl)

    def __call__(self, image: np.ndarray, roi) -> str:
        param = JOCR(roi=list(roi), only_rec=True, threshold=0.0)
        task = self.tasker.post_recognition(JRecognitionType.OCR, param, image).wait().get()
        reco = task.nodes[0].recognition if task and task.nodes else None
        return "".join(r.text for r in (reco.all_results if reco else []))


def load_bgr(path: str) -> np.ndarray:
    return np.ascontiguousarray(np.array(Image.open(path).convert("RGB"))[:, :, ::-1])


def main(mode: str, patterns: list[str]) -> None:
    ocr = Ocr()
    for path in [p for pattern in patterns for p in sorted(glob.glob(pattern))]:
        image = load_bgr(path)
        print(f"== {Path(path).name}")
        if mode == "list":
            print("  人數：", parse_member_count(ocr(image, F.MEMBER_COUNT_ROI)))
            for top in F.find_row_tops(image):
                name = ocr(image, F.row_name_roi(top))
                role = ocr(image, F.row_role_roi(top))
                contribution = ocr(image, F.row_contribution_roi(top))
                print(f"  列 y={top}：暱稱「{name}」職位「{role}」→{parse_role(role)} 貢獻度「{contribution}」")
        else:
            tab = ocr(image, F.PROFILE_TAB_ROI)
            name = ocr(image, F.PROFILE_NAME_ROI)
            uid_text = ocr(image, F.PROFILE_ID_ROI)
            print(f"  分頁「{tab}」暱稱「{name}」→{parse_name(name)} ID「{uid_text}」→{parse_uid(uid_text)}"
                  f"（OCR）／{read_uid(np.array(image[:, :, ::-1]))}（數字字卡，實際採用）")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
