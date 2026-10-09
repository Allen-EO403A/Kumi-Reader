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

"""下載 OCR 模型（PP-OCRv6 medium，MaaCommonAssets）到 assets/resource/model/ocr/。

模型檔很大，不放進 git；第一次開發或打包前執行一次：python tools/download_ocr_model.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/MaaXYZ/MaaCommonAssets/main/OCR/ppocr_v6"
# 辨識用 medium。只辨識不偵測，但 MaaFramework 載入時需要偵測模型：放 tiny 的（1.8 MB，不會被用到）
FILES = {
    "rec.onnx": ("medium", 76541685),
    "keys.txt": ("medium", 74947),
    "det.onnx": ("tiny", 1793196),
}

TARGET = Path(__file__).resolve().parents[1] / "assets" / "resource" / "model" / "ocr"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, (variant, size) in FILES.items():
        path = TARGET / name
        if path.exists() and path.stat().st_size == size:
            print(f"已存在：{name}")
            continue
        print(f"下載 {name}（{size / 1_000_000:.1f} MB）…")
        tmp = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(f"{BASE}/{variant}/{name}", tmp)
        if tmp.stat().st_size != size:
            tmp.unlink()
            print(f"下載的 {name} 大小不符，請重試。", file=sys.stderr)
            return 1
        tmp.replace(path)
    print(f"完成：{TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
