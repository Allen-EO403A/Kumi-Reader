from key_setup import mask, setup_key, write_env

KEY = "kumi_abcd1234_" + "A" * 43
OLD = "kumi_zzzz9999_" + "B" * 43


def test_write_env_replaces_key_and_keeps_other_lines(tmp_path):
    (tmp_path / ".env").write_text(f"# 說明\nKUMI_API_URL=https://api.example.org\nKUMI_READER_KEY={OLD}\n", encoding="utf-8")
    write_env(tmp_path, KEY, None)
    assert (tmp_path / ".env").read_text(encoding="utf-8") == f"# 說明\nKUMI_API_URL=https://api.example.org\nKUMI_READER_KEY={KEY}\n"


def test_write_env_creates_file_with_url(tmp_path):
    write_env(tmp_path, KEY, "https://api.example.org")
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert f"KUMI_READER_KEY={KEY}" in text
    assert "KUMI_API_URL=https://api.example.org" in text


def test_setup_key_rejects_clipboard_without_key(tmp_path, capsys):
    assert not setup_key(tmp_path, "隨便複製的文字", "https://api.example.org")
    assert not (tmp_path / ".env").exists()
    assert "剪貼簿裡沒有讀取程式金鑰" in capsys.readouterr().out


def test_setup_key_never_prints_the_whole_key(tmp_path, capsys):
    assert setup_key(tmp_path, f"  {KEY}\n", "https://api.example.org/")
    out = capsys.readouterr().out
    assert KEY not in out
    assert mask(KEY) in out
    assert "KUMI_API_URL=https://api.example.org\n" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_setup_key_without_url_asks_for_it(tmp_path, capsys):
    assert not setup_key(tmp_path, KEY, None)
    assert "KUMI_API_URL" in capsys.readouterr().out
