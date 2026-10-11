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

"""從個人資訊頁的實機截圖產生 UID 數字字卡（agent/kumi_reader/uid_digits.png）。

用法：
  python tools/build_uid_digits.py samples/profile-2.png=413506985892 samples/profile-3.png=271404104107 ...

每張截圖要附上人工核對過的正確 UID。0～9 每個數字都要至少出現在兩張截圖中。
產生前先做留一驗證：每張截圖都用「其他截圖做成的字卡」辨識，全部正確才寫入，並列出分數。
字卡是多張截圖的平均字形，不含任何一位玩家的 UID。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from kumi_reader import uid_digits as U  # noqa: E402


def load_rgb(path: str) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def build(samples: list[tuple[np.ndarray, str]]) -> dict[str, np.ndarray]:
    glyphs: dict[str, list[np.ndarray]] = {str(d): [] for d in range(10)}
    for image, uid in samples:
        for cell, digit in zip(U.cut_cells(image, pad=0), uid):
            glyphs[digit].append(cell)
    missing = [d for d, cells in glyphs.items() if not cells]
    if missing:
        sys.exit(f"截圖中沒有這些數字：{'、'.join(missing)}")
    return {d: np.mean(cells, axis=0) for d, cells in glyphs.items()}


def main(args: list[str]) -> None:
    if len(args) < 3:
        sys.exit(__doc__)
    samples = []
    for arg in args:
        path, _, uid = arg.partition("=")
        if len(uid) != U.UID_LENGTH or not uid.isdigit():
            sys.exit(f"{arg}：要寫成「截圖路徑=12 碼 UID」")
        samples.append((load_rgb(path), uid))

    lowest_correct, highest_wrong, failed = 1.0, 0.0, False
    for i, (image, uid) in enumerate(samples):
        templates = build(samples[:i] + samples[i + 1 :])
        got = ""
        for cell in U.cut_cells(image):
            scores = sorted(((U.match(cell, t), d) for d, t in templates.items()), reverse=True)
            got += scores[0][1]
            lowest_correct = min(lowest_correct, scores[0][0])
            highest_wrong = max(highest_wrong, scores[1][0])
        ok = got == uid
        failed |= not ok
        print(f"{'正確' if ok else '錯誤'}：{args[i].partition('=')[0]} 應為 {uid}，讀到 {got}")
    print(f"正確數字的最低分數 {lowest_correct:.3f}；最像的錯誤數字最高 {highest_wrong:.3f}")
    print(f"（採用門檻：分數 ≥ {U.MIN_SCORE}、與次像差距 ≥ {U.MIN_MARGIN}）")
    if failed:
        sys.exit("留一驗證有錯，不寫入字卡。")

    templates = build(samples)
    strip = np.concatenate([templates[str(d)] for d in range(10)], axis=1)
    Image.fromarray(np.round(strip * 255).astype(np.uint8), mode="L").save(U.TEMPLATE_PATH)
    print(f"已寫入 {U.TEMPLATE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
