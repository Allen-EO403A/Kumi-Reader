"""用 MaaFramework 的 OCR 離線辨識截圖中的固定區域，列出結果供人工比對。

用法：
  python tools/check_samples.py "samples/abyss-*.png"   # 深淵排行：每一列的暱稱、職位、傷害、挑戰次數
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

import abyss_flow as F  # noqa: E402
from kumi_reader.text import parse_int, parse_name, parse_role  # noqa: E402


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


def main(patterns: list[str]) -> None:
    ocr = Ocr()
    for path in [p for pattern in patterns for p in sorted(glob.glob(pattern))]:
        image = load_bgr(path)
        header = ocr(image, F.HEADER_ROI)
        print(f"== {Path(path).name}（表頭「{header}」，家族狀況分頁：{F.on_family_tab(image, header)}）")
        for top in F.find_row_tops(image):
            name = ocr(image, F.row_name_roi(top))
            role = ocr(image, F.row_role_roi(top))
            damage = ocr(image, F.row_damage_roi(top))
            challenges = ocr(image, F.row_challenges_roi(top))
            print(
                f"  列 y={top}：暱稱「{name}」→{parse_name(name)} 職位「{role}」→{parse_role(role)} "
                f"傷害「{damage}」→{parse_int(damage)} 挑戰「{challenges}」→{parse_int(challenges)}"
            )


if __name__ == "__main__":
    main(sys.argv[1:])
