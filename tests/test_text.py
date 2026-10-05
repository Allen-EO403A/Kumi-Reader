from kumi_reader.text import clean, parse_int, parse_member_count, parse_name, parse_role, parse_uid


def test_parse_uid_accepts_ocr_variants():
    # 取自 OCR 比較時各模型的實際輸出
    assert parse_uid("ID：413506985892") == "413506985892"
    assert parse_uid("ID:413506985892") == "413506985892"
    assert parse_uid("1D：413506985892") == "413506985892"
    assert parse_uid("I413506985892") == "413506985892"
    assert parse_uid("|D:260706551110") == "260706551110"
    assert parse_uid("ＩＤ：１２３４５６７８９０１２") == "123456789012"
    # 沒有 ID 前綴、開頭是 1 的 UID 不能被誤刪
    assert parse_uid("100000000000") == "100000000000"


def test_parse_uid_rejects_wrong_length_or_ambiguous():
    assert parse_uid("ID：41350698589") is None  # 11 碼
    assert parse_uid("ID::2626070606551110") is None  # 數字重複成 16 碼
    assert parse_uid("") is None
    assert parse_uid("ID：123456789012 123456789012") is None


def test_parse_int():
    assert parse_int("2736399") == 2736399
    assert parse_int("１") == 1
    assert parse_int("3㎡") is None
    assert parse_int("") is None


def test_parse_member_count():
    assert parse_member_count("成員：99/100") == (99, 100)
    assert parse_member_count("成員:99 / 100") == (99, 100)
    assert parse_member_count("成員") is None


def test_parse_role():
    assert parse_role("精英") == "精英"
    assert parse_role("豪傑樂") == "豪傑"  # 後面多讀一個字
    assert parse_role("副族長") == "副族長"  # 不能被「族長」先吃掉
    assert parse_role("豪") is None


def test_parse_name_and_clean():
    assert parse_name("  霜刃・伊鶴 ") == "霜刃・伊鶴"
    assert parse_name("​") is None
    assert clean("ｂｏｔ＿Ａｎ９ｕＳ") == "bot_An9uS"
    assert clean("海・闇梟♪") == "海・闇梟♪"  # 不改動中日文與符號
