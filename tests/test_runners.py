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

"""讀取與上傳分開：讀取任務只存本機，「上傳讀取結果」才上傳（decisions.md 第 19 節）。"""
from datetime import datetime, timezone

import responses

import local_results as store
from abyss_runner import read_abyss
from fake_abyss import FakeAbyss, make_entries
from fake_game import FakeGame, Page, make_rows
from kumi_reader.device import StopRequested
from members_runner import read_members
from upload_runner import upload_all

URL = "https://api.example.org"
KEY = "kumi_abcd1234_" + "A" * 43
TOPS = [324, 437, 550, 663, 777, 890]
WHOAMI = {"keyName": "辦公室電腦", "holderDiscordId": "1" * 18, "program": "members", "boundAt": None}
MEMBER_RES = {
    "batchId": 5, "status": "complete", "readCount": 6, "expectedCount": 6, "countMismatch": False,
    "newMembers": 6, "renamed": 0, "rejoined": 0, "markedLeft": 0, "nameUnreadable": 0,
}
ABYSS_RES = {
    "batchId": 9, "status": "pending", "periodStart": "2026-10-02",
    "inserted": 9, "replaced": 0, "matched": 9, "unmatched": 0, "ambiguous": 0, "skippedConfirmed": 0,
}


def make_root(tmp_path):
    (tmp_path / ".env").write_text(f"KUMI_API_URL={URL}\nKUMI_READER_KEY={KEY}\n", encoding="utf-8")
    return tmp_path


def test_reading_members_only_saves_locally(tmp_path):
    data = tmp_path / "data"
    assert read_members(FakeGame([Page(TOPS, make_rows(6))], expected=6), data, None, resume=False)
    saved = store.load_members(data)
    assert saved["complete"] and saved["pending"]
    assert len(saved["members"]) == 6


def test_new_read_stops_when_local_result_not_uploaded(tmp_path, capsys):
    data = tmp_path / "data"
    rows = make_rows(6)
    read_members(FakeGame([Page(TOPS, rows)], expected=8), data, None, resume=False)
    game = FakeGame([Page(TOPS, rows)], expected=8)
    assert not read_members(game, data, None, resume=False)
    assert game.clicks == []
    assert "沒有上傳" in capsys.readouterr().out
    # 選「捨棄本機結果重新讀取」時重新開始
    assert read_members(FakeGame([Page(TOPS, rows)], expected=6), data, None, resume=False, discard=True)
    assert store.load_members(data)["complete"]


def test_missing_members_need_local_progress(tmp_path, capsys):
    assert not read_members(FakeGame([Page(TOPS, make_rows(6))], expected=6), tmp_path, None, resume=True)
    assert "請先執行「讀取家族成員」" in capsys.readouterr().out


@responses.activate
def test_upload_sends_members_and_clears_when_complete(tmp_path, capsys):
    root = make_root(tmp_path)
    read_members(FakeGame([Page(TOPS, make_rows(6))], expected=6), root / "data", None, resume=False)
    responses.get(f"{URL}/api/reader/whoami", json=WHOAMI)
    upload = responses.post(f"{URL}/api/reader/member-batches", json=MEMBER_RES)
    assert upload_all(root)
    assert upload.calls[0].request.headers["X-Kumi-Program"] == "members"
    assert store.load_members(root / "data") is None
    assert KEY not in capsys.readouterr().out


@responses.activate
def test_incomplete_upload_keeps_progress_for_missing_members(tmp_path):
    root = make_root(tmp_path)
    read_members(FakeGame([Page(TOPS, make_rows(6))], expected=8), root / "data", None, resume=False)
    responses.get(f"{URL}/api/reader/whoami", json=WHOAMI)
    upload = responses.post(f"{URL}/api/reader/member-batches", json={**MEMBER_RES, "status": "incomplete", "expectedCount": 8})
    assert upload_all(root)
    assert b'"status": "incomplete"' in upload.calls[0].request.body
    saved = store.load_members(root / "data")
    assert saved["batchId"] == 5 and not saved["pending"]
    # 上傳過的進度可以補讀；之後上傳接續同一批次
    assert not upload_all(root)  # 沒有新的結果可上傳


@responses.activate
def test_failed_upload_keeps_local_result(tmp_path):
    root = make_root(tmp_path)
    read_members(FakeGame([Page(TOPS, make_rows(6))], expected=6), root / "data", None, resume=False)
    responses.get(f"{URL}/api/reader/whoami", json=WHOAMI)
    responses.post(f"{URL}/api/reader/member-batches", status=503, json={"code": "X", "message": "暫時無法使用"})
    assert not upload_all(root)
    assert store.load_members(root / "data")["pending"]


@responses.activate
def test_abyss_upload_checks_period(tmp_path, capsys):
    root = make_root(tmp_path)
    read_at = datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc)  # 10/3（六）12:00 台灣時間
    assert read_abyss(FakeAbyss(make_entries(9)), root / "data", now=read_at)
    assert store.load_abyss(root / "data")["periodStart"] == "2026-10-02"
    responses.get(f"{URL}/api/reader/whoami", json={**WHOAMI, "program": "abyss"})
    responses.get(f"{URL}/api/reader/abyss-batches/current", json={"periodStart": "2026-10-02", "batchId": None, "lastRank": None})
    upload = responses.post(f"{URL}/api/reader/abyss-batches", json=ABYSS_RES)
    assert upload_all(root)
    assert upload.calls[0].request.headers["X-Kumi-Program"] == "abyss"
    assert store.load_abyss(root / "data") is None


@responses.activate
def test_abyss_result_from_previous_period_is_not_uploaded(tmp_path, capsys):
    root = make_root(tmp_path)
    read_abyss(FakeAbyss(make_entries(9)), root / "data", now=datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc))
    responses.get(f"{URL}/api/reader/whoami", json={**WHOAMI, "program": "abyss"})
    responses.get(f"{URL}/api/reader/abyss-batches/current", json={"periodStart": "2026-10-09", "batchId": None, "lastRank": None})
    assert not upload_all(root)
    assert len(responses.calls) == 2  # 沒有上傳
    assert "無法上傳" in capsys.readouterr().out


def test_abyss_period_starts_friday_20():
    assert store.abyss_period_start(datetime(2026, 10, 9, 11, 59, tzinfo=timezone.utc)) == "2026-10-02"  # 10/9 19:59
    assert store.abyss_period_start(datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)) == "2026-10-09"  # 10/9 20:00
    assert store.abyss_period_start(datetime(2026, 10, 4, 18, 0, tzinfo=timezone.utc)) == "2026-10-02"  # 10/5 02:00


class StoppingGame(FakeGame):
    """第 n 次點擊時模擬使用者按下停止。"""

    def __init__(self, *args, stop_after: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.stop_after = stop_after

    def click(self, x, y):
        if len(self.clicks) >= self.stop_after:
            raise StopRequested()
        super().click(x, y)


def test_stop_keeps_members_read_so_far(tmp_path, capsys):
    data = tmp_path / "data"
    rows = make_rows(6)
    game = StoppingGame([Page(TOPS, rows)], expected=6, stop_after=7)  # 讀完 2 人後停止
    assert not read_members(game, data, None, resume=False)
    assert len(game.clicks) == 7
    saved = store.load_members(data)
    assert len(saved["members"]) == 2 and saved["pending"] and not saved["complete"]
    assert "已依要求停止" in capsys.readouterr().out
    # 補讀接著讀剩下的人
    assert read_members(FakeGame([Page(TOPS, rows)], expected=6), data, None, resume=True)
    assert store.load_members(data)["complete"]


class StoppingAbyss(FakeAbyss):
    def drag(self, x, y1, y2):
        if self.drags_done >= 2:
            raise StopRequested()
        self.drags_done += 1
        super().drag(x, y1, y2)


def test_stop_during_abyss_saves_rows_read_so_far(tmp_path, capsys):
    game = StoppingAbyss(make_entries(20))
    game.drags_done = 0
    assert not read_abyss(game, tmp_path, now=datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc))
    saved = store.load_abyss(tmp_path)
    assert saved["body"]["status"] == "incomplete"
    assert 0 < len(saved["body"]["rows"]) < 20
    assert "已依要求停止" in capsys.readouterr().out
