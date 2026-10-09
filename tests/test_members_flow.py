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

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import members_flow as F
from fake_game import BG, LINE, FakeGame, Page, make_rows

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "member-list.png"
TOPS = [324, 437, 550, 663, 777, 890]  # 實機截圖量到的分隔線
# 禁止點擊區（reader.md）：備註鉛筆、加好友、暱稱下拉、搭配分頁的詳情；以及小視窗的「踢出家族」
FORBIDDEN = [(1450, 383), (1705, 387), (1482, 253), (1534, 805), (1493, 570)]


def synthetic(tops):
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    image[:, :] = BG
    for top in tops:
        image[top : top + 2, :] = LINE
    return image


def test_find_row_tops_on_synthetic_image():
    # 7 條線 → 6 列完整露出
    assert F.find_row_tops(synthetic(TOPS + [1004])) == TOPS
    # 滑動到一半：最上面與最下面的列被切掉，不算
    assert F.find_row_tops(synthetic([350, 463, 577, 690, 804, 917])) == [350, 463, 577, 690, 804]


def test_find_row_tops_handles_top_of_list_and_highlighted_row():
    # 名單在最上面：第一列上方沒有分隔線；自己那一列是藍底（不能被當成分隔線）
    image = synthetic([399, 513, 626, 740, 853, 966])
    image[628:740, :] = (167, 127, 110)  # BGR，藍底列約 RGB(110,127,167)
    image[288:399, :] = (223, 241, 245)  # 列背景亮度與其他截圖不同
    assert F.find_row_tops(image) == [286, 399, 513, 626, 740, 853]


def test_long_name_reaching_into_blank_column_is_not_a_separator():
    # 長暱稱的文字延伸到暱稱右邊的空白欄：只要分隔線欄位乾淨，就不會多出假分隔線
    image = synthetic([399, 513, 626, 740, 853, 966])
    image[420:450, 690:1045] = (170, 199, 203)  # 文字邊緣的顏色剛好接近分隔線
    assert F.find_row_tops(image) == [286, 399, 513, 626, 740, 853]


@pytest.mark.skipif(not SAMPLE.exists(), reason="需要 samples/member-list.png（實機截圖，不提交）")
def test_find_row_tops_on_real_screenshot():
    rgb = np.array(Image.open(SAMPLE).convert("RGB"))
    assert F.find_row_tops(rgb[:, :, ::-1].copy()) == [323, 437, 550, 663, 777, 890]


def test_reads_every_member_across_pages_without_duplicates():
    rows = make_rows(9)
    pages = [
        Page(TOPS, rows[0:6]),
        Page([350, 463, 577, 690, 804], rows[4:9]),  # 與上一頁重疊兩列
    ]
    game = FakeGame(pages, expected=9)
    result = F.MembersReader(game).run()
    assert result.complete
    assert result.stop_reason is None
    assert sorted(result.members) == sorted(r.uid for r in rows)
    assert result.members[rows[1].uid] == {"uid": rows[1].uid, "name": "成員1", "role": "精英"}
    # 重疊的兩列不重開個人視窗：每人點 3 下（頭像、個人資訊、關閉）
    assert len(game.clicks) == 9 * 3
    assert not set(game.clicks) & set(FORBIDDEN)


def test_stops_instead_of_skipping_when_pages_do_not_overlap():
    rows = make_rows(12)
    # 第二頁與第一頁沒有重疊（滑過頭），往回拖也回不去
    game = FakeGame([Page(TOPS, rows[0:6]), Page(TOPS, rows[8:12])], expected=12, drag_back_works=False)
    result = F.MembersReader(game).run()
    assert result.stop_reason and "漏讀" in result.stop_reason
    assert sorted(result.members) == sorted(r.uid for r in rows[0:6])  # 不讀可能漏人的那一頁
    assert any(y2 > y1 for y1, y2 in game.drags)  # 有試著往回拖


def test_uses_drag_and_moves_less_than_a_page():
    rows = make_rows(9)
    game = FakeGame([Page(TOPS, rows[0:6]), Page([350, 463, 577, 690, 804], rows[4:9])], expected=9)
    F.MembersReader(game).run()
    y1, y2 = next((a, b) for a, b in game.drags if b < a)  # 第一次往下捲
    assert 0 < y1 - y2 < 6 * F.ROW_HEIGHT  # 一次拖動少於一頁（6 列）


def test_scrolls_to_top_before_reading():
    rows = make_rows(9)
    pages = [Page(TOPS, rows[0:6]), Page([350, 463, 577, 690, 804], rows[4:9])]
    game = FakeGame(pages, expected=9, page=1)  # 開始時停在名單底部
    result = F.MembersReader(game).run()
    assert result.complete
    assert sorted(result.members) == sorted(r.uid for r in rows)


def test_stops_at_bottom_when_scrolling_changes_nothing():
    rows = make_rows(6)
    game = FakeGame([Page(TOPS, rows)], expected=8)  # 應讀 8 人，但名單只有 6 列
    result = F.MembersReader(game).run()
    assert not result.complete  # 已到底但人數不符：不算讀完
    assert "少 2 人" in result.stop_reason
    assert len(result.members) == 6
    body = F.build_upload(result, batch_id=None)
    assert body["status"] == "incomplete"
    assert body["expectedCount"] == 8
    assert "batchId" not in body


def test_resumes_without_reopening_known_members():
    rows = make_rows(6)
    first = F.MembersReader(FakeGame([Page(TOPS, rows)], expected=6))
    saved = {}
    first.on_progress = lambda result, done: saved.update(members=dict(result.members), done=set(done))
    first.run()
    game = FakeGame([Page(TOPS, rows)], expected=6)
    result = F.MembersReader(game, done_keys=saved["done"], known=saved["members"]).run()
    assert result.complete
    assert len(result.members) == 6
    assert game.clicks == []  # 都讀過了：不再開個人視窗


def test_unreadable_uid_is_counted_as_failed_row():
    rows = make_rows(6)
    rows[2].uid_readable = False
    game = FakeGame([Page(TOPS, rows)], expected=6)
    result = F.MembersReader(game).run()
    assert result.failed_rows == 3  # 第一次＋回到最上面再找的兩次都重試
    assert rows[2].uid not in result.members
    assert len(result.members) == 5


def test_refuses_to_start_outside_member_list():
    game = FakeGame([Page(TOPS, make_rows(6))], expected=6, on_list_at_start=False)
    result = F.MembersReader(game).run()
    assert result.stop_reason and "成員" in result.stop_reason
    assert game.clicks == []


def test_build_upload_resumes_incomplete_batch():
    result = F.MembersResult(expected=99, members={"200000000000": {"uid": "200000000000", "name": None, "role": None}})
    body = F.build_upload(result, batch_id=7)
    assert body == {
        "status": "incomplete",
        "expectedCount": 99,
        "members": [{"uid": "200000000000", "name": None, "role": None}],
        "batchId": 7,
    }


def test_resume_scrolls_whole_list_and_reads_only_missing_members():
    rows = make_rows(9)
    pages = [Page(TOPS, rows[0:6]), Page([350, 463, 577, 690, 804], rows[4:9])]
    first = F.MembersReader(FakeGame(pages, expected=9))
    saved = {}
    first.on_progress = lambda result, done: saved.update(members=dict(result.members), done=set(done))
    first.run()
    # 先前少讀了第二頁的一位
    missing = rows[7]
    saved["members"].pop(missing.uid)
    saved["done"] = {k for k in saved["done"] if k[0] != missing.name}

    game = FakeGame(pages, expected=9, page=1)  # 開始時停在哪一頁都可以
    result = F.MembersReader(game, done_keys=saved["done"], known=saved["members"]).run()
    assert result.complete
    assert missing.uid in result.members
    assert len(game.clicks) == 3  # 只開了缺少那一位的個人視窗
    assert any(y2 < y1 for y1, y2 in game.drags)  # 有往下滑找


def test_failed_row_is_retried_when_resuming():
    rows = make_rows(6)
    rows[2].uid_readable = False
    saved = {}
    first = F.MembersReader(FakeGame([Page(TOPS, rows)], expected=6))
    first.on_progress = lambda result, done: saved.update(members=dict(result.members), done=set(done))
    assert not first.run().complete

    rows[2].uid_readable = True
    game = FakeGame([Page(TOPS, rows)], expected=6)
    result = F.MembersReader(game, done_keys=saved["done"], known=saved["members"]).run()
    assert result.complete
    assert rows[2].uid in result.members


def test_expected_count_entered_by_admin_wins():
    rows = make_rows(6)
    game = FakeGame([Page(TOPS, rows)], expected=6)  # 畫面上是 6
    result = F.MembersReader(game, expected_override=7).run()
    assert result.expected == 7
    assert not result.complete and "少 1 人" in result.stop_reason


class ReorderingGame(FakeGame):
    """第一次往下滑時，名單底部的人上線、移到最上面（已經讀過的區域）。"""

    def drag(self, x, y1, y2):
        if y2 < y1 and not getattr(self, "reordered", False):
            self.reordered = True
            rows = self.all_rows
            self.pages = [
                Page(TOPS, [rows[8]] + rows[0:5]),
                Page([350, 463, 577, 690, 804], rows[3:8]),
            ]
        super().drag(x, y1, y2)


def test_rescans_from_top_when_list_order_changes_while_reading():
    rows = make_rows(9)
    game = ReorderingGame([Page(TOPS, rows[0:6]), Page([350, 463, 577, 690, 804], rows[4:9])], expected=9)
    game.all_rows = rows
    result = F.MembersReader(game).run()
    assert result.complete
    assert sorted(result.members) == sorted(r.uid for r in rows)
    assert len(game.clicks) == 9 * 3  # 每人只開一次個人視窗


def test_gives_up_after_extra_passes():
    rows = make_rows(6)
    game = FakeGame([Page(TOPS, rows)], expected=8)
    result = F.MembersReader(game, extra_passes=2).run()
    assert not result.complete and "少 2 人" in result.stop_reason
    assert len(game.clicks) == 6 * 3  # 再找時不重開已讀的人
