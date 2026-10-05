from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import abyss_flow as F
from fake_abyss import TOPS, FakeAbyss, make_entries

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "abyss-bottom.png"


@pytest.mark.skipif(not SAMPLE.exists(), reason="需要 samples/abyss-bottom.png（實機截圖，不提交）")
def test_real_screenshot_rows_and_tab():
    image = np.array(Image.open(SAMPLE).convert("RGB"))[:, :, ::-1].copy()
    # 最上面被切掉的列與底部黃色的自己都不算
    assert F.find_row_tops(image) == [196, 331, 466, 601, 736]
    assert F.on_family_tab(image, "傷害")


def test_reads_whole_list_in_order_from_the_top():
    entries = make_entries(13)
    game = FakeAbyss(entries, offset=8)  # 開始時停在名單中間
    result = F.AbyssReader(game).run()
    assert result.complete and result.stop_reason is None
    assert [r.rank for r in result.rows] == list(range(1, 14))
    assert [r.name for r in result.rows] == [e.name for e in entries]
    assert result.rows[0].role == "精英"
    assert result.rows[2].damage == 8_900_000
    assert game.clicks == []  # 程式 B 不點擊


def test_skips_a_repeated_row_even_if_its_name_reads_differently():
    entries = make_entries(9)
    # 第 5 名在第二頁重複出現時暱稱讀成別的字
    entries[4].second_look_name = "玩家五"
    result = F.AbyssReader(FakeAbyss(entries)).run()
    assert [r.rank for r in result.rows] == list(range(1, 10))
    assert len(result.rows) == 9


def test_stops_and_keeps_rows_when_a_number_is_unreadable():
    entries = make_entries(9)
    entries[6].unreadable_damage = True
    result = F.AbyssReader(FakeAbyss(entries)).run()
    assert not result.complete
    assert "第 7 名" in result.stop_reason
    assert len(result.rows) == 6
    body = F.build_upload(result, batch_id=3)
    assert body["status"] == "incomplete"
    assert body["lastRank"] == 6
    assert body["batchId"] == 3


def test_stops_instead_of_skipping_when_pages_do_not_overlap():
    entries = make_entries(20)
    game = FakeAbyss(entries, overshoot=4, drag_back_works=False)  # 每次多滑 4 列、回不去
    result = F.AbyssReader(game).run()
    assert "名次錯位" in result.stop_reason
    assert [r.name for r in result.rows] == [e.name for e in entries[:5]]  # 只保留確定連續的部分


def test_refuses_to_start_on_another_tab():
    game = FakeAbyss(make_entries(5), family_tab=False)
    result = F.AbyssReader(game).run()
    assert "家族狀況" in result.stop_reason
    assert result.rows == []


def test_build_upload_shape():
    result = F.AbyssResult(rows=[F.AbyssRow(1, "千夏", "族員", 2736399, 2), F.AbyssRow(2, None, None, 100, 1)], complete=True)
    assert F.build_upload(result, batch_id=None) == {
        "status": "complete",
        "lastRank": 2,
        "rows": [
            {"rank": 1, "name": "千夏", "role": "族員", "damage": 2736399, "challengeCount": 2},
            {"rank": 2, "name": None, "role": None, "damage": 100, "challengeCount": 1},
        ],
    }


def test_find_row_tops_on_synthetic_offsets():
    image = FakeAbyss(make_entries(5)).screencap()
    assert F.find_row_tops(image) == TOPS
