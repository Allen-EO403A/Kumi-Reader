"""打包給管理員使用的資料夾與 zip（decisions.md 第 19 節）。

內容：MFAAvalonia v2.16.2（介面）＋MaaFramework 5.14.2 執行檔（取代 MFAAvalonia 內附的版本，
與 Python 端的 MaaFw 版本一致）＋Python 3.13 嵌入版與套件＋本程式（agent、resource、interface.json）。

用法（在本 repo 的開發環境中，需為 Windows x64 的 Python 3.13）：
  python tools/download_ocr_model.py
  python tools/build_package.py 0.1.0
輸出：install/（可直接執行）與 dist/<repo 名稱>-v<版本>.zip。下載的檔案快取在 .cache/。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

MAAFW_VERSION = "5.14.2"
MFA_VERSION = "2.16.2"
PYTHON_VERSION = "3.13.16"

DOWNLOADS = {
    "maafw": f"https://github.com/MaaXYZ/MaaFramework/releases/download/v{MAAFW_VERSION}/MAA-win-x86_64-v{MAAFW_VERSION}.zip",
    "mfa": f"https://github.com/MaaXYZ/MFAAvalonia/releases/download/v{MFA_VERSION}/MFAAvalonia-v{MFA_VERSION}-win-x64.zip",
    "python": f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip",
}

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
INSTALL = ROOT / "install"
DIST = ROOT / "dist"


def download(name: str) -> Path:
    url = DOWNLOADS[name]
    path = CACHE / url.rsplit("/", 1)[1]
    if not path.exists():
        CACHE.mkdir(exist_ok=True)
        print(f"下載 {path.name} …")
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(path)
    return path


def extract(archive: Path, target: Path) -> None:
    with zipfile.ZipFile(archive) as z:
        z.extractall(target)


def install_mfa() -> None:
    extract(download("mfa"), INSTALL)
    # 換掉 MFAAvalonia 內附的 MaaFramework（agent 通訊協定版本必須與 Python 端一致）
    shutil.rmtree(INSTALL / "runtimes", ignore_errors=True)


def install_maafw() -> None:
    tmp = CACHE / f"maafw-{MAAFW_VERSION}"
    if not tmp.exists():
        extract(download("maafw"), tmp)
    shutil.copytree(
        tmp / "bin",
        INSTALL / "runtimes" / "win-x64" / "native",
        ignore=shutil.ignore_patterns(
            "*MaaDbgControlUnit*", "*MaaThriftControlUnit*", "*MaaRpc*", "*MaaHttp*", "plugins", "*.node", "*MaaPiCli*"
        ),
        dirs_exist_ok=True,
    )
    shutil.copytree(tmp / "share" / "MaaAgentBinary", INSTALL / "libs" / "MaaAgentBinary", dirs_exist_ok=True)
    if (tmp / "bin" / "plugins").exists():
        shutil.copytree(tmp / "bin" / "plugins", INSTALL / "plugins" / "win-x64", dirs_exist_ok=True)


def install_python() -> None:
    target = INSTALL / "python"
    extract(download("python"), target)
    # 嵌入版預設不載入 site-packages：加上路徑並啟用 site
    pth = next(target.glob("python3*._pth"))
    lines = [line for line in pth.read_text(encoding="utf-8").splitlines() if line.strip() != "#import site"]
    pth.write_text("\n".join(lines + ["Lib\\site-packages", "import site"]) + "\n", encoding="utf-8")
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
            "--target", str(target / "Lib" / "site-packages"),
            "-r", str(ROOT / "requirements.txt"),
        ],
        check=True,
    )


def install_app(version: str) -> None:
    model = ROOT / "assets" / "resource" / "model" / "ocr" / "rec.onnx"
    if not model.exists():
        sys.exit("找不到 OCR 模型，請先執行 python tools/download_ocr_model.py")
    shutil.copytree(
        ROOT / "assets" / "resource", INSTALL / "resource",
        ignore=shutil.ignore_patterns(".gitkeep"), dirs_exist_ok=True,
    )
    interface = json.loads((ROOT / "assets" / "interface.json").read_text(encoding="utf-8"))
    interface["version"] = version
    (INSTALL / "interface.json").write_text(json.dumps(interface, ensure_ascii=False, indent=4), encoding="utf-8")
    shutil.copytree(
        ROOT / "agent", INSTALL / "agent",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"), dirs_exist_ok=True,
    )
    shutil.copy2(ROOT / ".env.example", INSTALL / ".env.example")
    shutil.copy2(ROOT / "README.md", INSTALL / "README.md")


def verify() -> None:
    """用打包好的 Python 確認套件與程式都能載入。"""
    python = INSTALL / "python" / "python.exe"
    code = (
        "import sys; sys.path.insert(0, 'agent'); "
        "import maa, requests, actions, members_runner, abyss_runner, key_setup; from importlib.metadata import version; "
        "print('MaaFw', version('MaaFw'), 'Python', sys.version.split()[0])"
    )
    subprocess.run([str(python), "-c", code], cwd=INSTALL, check=True)
    if not (INSTALL / "runtimes" / "win-x64" / "native" / "MaaFramework.dll").exists():
        sys.exit("打包內容缺少 MaaFramework.dll")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("用法：python tools/build_package.py <版本，例如 0.1.0>")
    if sys.version_info[:2] != (3, 13):
        sys.exit("請用 Python 3.13 執行（套件要與內附的 Python 3.13 相容）。")
    version = sys.argv[1].lstrip("v")
    shutil.rmtree(INSTALL, ignore_errors=True)
    INSTALL.mkdir()
    install_mfa()
    install_maafw()
    install_python()
    install_app(version)
    verify()
    DIST.mkdir(exist_ok=True)
    name = f"{ROOT.name}-v{version}"
    archive = shutil.make_archive(str(DIST / name), "zip", INSTALL)
    print(f"完成：{INSTALL}\n壓縮檔：{archive}")


if __name__ == "__main__":
    main()
