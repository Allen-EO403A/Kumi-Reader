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

"""產生發布用的安裝程式 dist/release/Kumi-Reader-Setup-v<版本>.exe（Inno Setup 6）。

步驟：tools/build_package.py 產生 install/ → 下載 .NET 10 Desktop Runtime 安裝檔並以官方 SHA-512 檢查
→ 以 ISCC 編譯 installer/kumi-reader.iss。

用法（Windows x64、Python 3.13，已安裝 Inno Setup 6，例如 `winget install JRSoftware.InnoSetup`）：
  python tools/download_ocr_model.py
  python tools/build_installer.py 0.4.0
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import build_package

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
# .NET 10 Desktop Runtime（MFAAvalonia 需要）；版本與檔案以微軟的發布資料為準
DOTNET_CHANNEL = "10.0"
DOTNET_RELEASES = (
    f"https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/{DOTNET_CHANNEL}/releases.json"
)


def dotnet_installer() -> Path:
    """下載最新的 .NET 10 Windows Desktop Runtime（x64）安裝檔，並以官方 SHA-512 檢查。"""
    with urllib.request.urlopen(DOTNET_RELEASES) as res:
        releases = json.load(res)
    latest = releases["releases"][0]["windowsdesktop"]
    file = next(
        f for f in latest["files"] if f["rid"] == "win-x64" and f["name"].endswith(".exe")
    )
    path = CACHE / f"windowsdesktop-runtime-{latest['version']}-win-x64.exe"
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        print(f"下載 .NET {latest['version']} Desktop Runtime …")
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(file["url"], tmp)
        tmp.replace(path)
    digest = hashlib.sha512(path.read_bytes()).hexdigest()
    if digest.lower() != file["hash"].lower():
        path.unlink()
        sys.exit(".NET 安裝檔的 SHA-512 與官方資料不符，已刪除，請重新執行。")
    return path


def iscc() -> Path:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    ]
    found = shutil.which("ISCC") or next((str(p) for p in candidates if p.exists()), None)
    if not found:
        sys.exit("找不到 Inno Setup 6 的 ISCC.exe，請先安裝：winget install JRSoftware.InnoSetup")
    return Path(found)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("用法：python tools/build_installer.py <版本，例如 0.4.0>")
    version = sys.argv[1].lstrip("v")
    compiler = iscc()
    sys.argv = [sys.argv[0], version]
    build_package.main()
    dotnet = dotnet_installer()
    subprocess.run(
        [
            str(compiler),
            "/Qp",
            f"/DAppVersion={version}",
            f"/DDotNetInstaller={dotnet}",
            str(ROOT / "installer" / "kumi-reader.iss"),
        ],
        check=True,
    )
    print(f"安裝程式：{ROOT / 'dist' / 'release' / f'Kumi-Reader-Setup-v{version}.exe'}")


if __name__ == "__main__":
    main()
