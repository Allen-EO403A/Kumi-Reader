"""讀取程式的設定：從程式資料夾的 `.env` 讀取後端網址與讀取程式金鑰。

金鑰是憑證：只放在 `.env`，不寫進程式、執行紀錄或錯誤訊息。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

KEY_PATTERN = re.compile(r"^kumi_[a-z0-9]{8}_[A-Za-z0-9_-]{43}$")


class ConfigError(Exception):
    """設定缺漏或格式錯誤；訊息會直接顯示給使用者，不含金鑰內容。"""


@dataclass(frozen=True)
class Config:
    api_url: str
    reader_key: str

    def __repr__(self) -> str:  # 避免金鑰出現在任何 repr／log 中
        return f"Config(api_url={self.api_url!r}, reader_key=***)"


def parse_env(text: str) -> dict[str, str]:
    """解析簡單的 KEY=VALUE 格式；忽略空行與 # 開頭的註解，值可加引號。"""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name.strip()] = value
    return values


def load_config(root: Path, environ: dict[str, str] | None = None) -> Config:
    """讀取 `<root>/.env`；同名的環境變數優先（方便開發時臨時覆寫）。"""
    env_file = root / ".env"
    values = parse_env(env_file.read_text(encoding="utf-8")) if env_file.exists() else {}
    environ = os.environ if environ is None else environ
    for name in ("KUMI_API_URL", "KUMI_READER_KEY"):
        if environ.get(name):
            values[name] = environ[name]

    api_url = values.get("KUMI_API_URL", "").strip().rstrip("/")
    reader_key = values.get("KUMI_READER_KEY", "").strip()
    if not api_url or not reader_key:
        raise ConfigError(
            f"找不到設定。請在 {env_file} 填寫 KUMI_API_URL（後端網址）與 KUMI_READER_KEY（網站產生的讀取程式金鑰）。"
        )
    parsed = urlparse(api_url)
    local = parsed.hostname in ("localhost", "127.0.0.1")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise ConfigError("KUMI_API_URL 必須是 https:// 開頭的網址（只有本機測試可用 http://localhost）。")
    if not KEY_PATTERN.match(reader_key):
        raise ConfigError("KUMI_READER_KEY 格式不正確。請從網站「讀取程式金鑰」頁重新複製完整金鑰。")
    return Config(api_url=api_url, reader_key=reader_key)
