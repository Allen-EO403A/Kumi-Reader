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

"""後端 API（kumi-api 的 /api/reader/*）。

每個請求都帶金鑰、程式種類與安裝識別碼（decisions.md 第 19 節）。
錯誤訊息直接採用後端回傳的中文 message；不在任何訊息中輸出金鑰。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import requests

Program = Literal["members", "abyss"]


class ApiError(Exception):
    """後端回傳錯誤，或連不上後端（status 為 0）。"""

    def __init__(self, status: int, code: str, message: str, fields: dict[str, str] | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.fields = fields or {}

    @property
    def retryable(self) -> bool:
        """連線問題或伺服器錯誤：稍後可以重送。其他錯誤重送也不會成功。"""
        return self.status == 0 or self.status >= 500

    def describe(self) -> str:
        if not self.fields:
            return self.message
        details = "；".join(f"{k}：{v}" for k, v in self.fields.items())
        return f"{self.message}（{details}）"


@dataclass(frozen=True)
class Whoami:
    key_name: str
    holder_discord_id: str
    program: str
    bound_at: str


class KumiApi:
    def __init__(
        self,
        api_url: str,
        reader_key: str,
        program: Program,
        instance_id: str,
        session: requests.Session | None = None,
        timeout: float = 30.0,
    ):
        self._base = api_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {reader_key}",
            "X-Kumi-Program": program,
            "X-Kumi-Instance": instance_id,
        }

    def _request(self, method: str, path: str, body: Any = None) -> Any:
        try:
            res = self._session.request(
                method,
                f"{self._base}{path}",
                json=body,
                headers=self._headers,
                timeout=self._timeout,
            )
        except requests.RequestException:
            raise ApiError(0, "NETWORK", "無法連線到後端，請確認網路或後端網址後再試一次。") from None
        if res.ok:
            return res.json() if res.content else None
        try:
            data = res.json()
        except ValueError:
            data = {}
        message = data.get("message") or f"後端回傳錯誤（HTTP {res.status_code}）"
        raise ApiError(res.status_code, data.get("code", "UNKNOWN"), message, data.get("fields"))

    def whoami(self) -> Whoami:
        """確認金鑰有效；第一次使用時同時把金鑰綁定到這一份程式。"""
        data = self._request("GET", "/api/reader/whoami")
        return Whoami(data["keyName"], data["holderDiscordId"], data["program"], data["boundAt"])

    def upload_member_batch(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/reader/member-batches", body)

    def upload_abyss_batch(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/reader/abyss-batches", body)

    def current_abyss_batch(self) -> dict[str, Any]:
        return self._request("GET", "/api/reader/abyss-batches/current")
