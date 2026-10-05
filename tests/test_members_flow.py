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


def test_stops_at_bottom_when_scrolling_changes_nothing():
    rows = make_rows(6)
    game = FakeGame([Page(TOPS, rows)], expected=8)  # 應讀 8 人，但名單只有 6 列
    result = F.MembersReader(game).run()
    assert result.complete  # 已到底
    assert len(result.members) == 6
    body = F.build_upload(result, batch_id=None)
    assert body["status"] == "complete"
    assert body["expectedCount"] == 8
    assert "batchId" not in body


def test_unreadable_uid_is_counted_as_failed_row():
    rows = make_rows(6)
    rows[2].uid_readable = False
    game = FakeGame([Page(TOPS, rows)], expected=6)
    result = F.MembersReader(game).run()
    assert result.failed_rows == 1
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
