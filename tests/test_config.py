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

import pytest

from kumi_reader.config import Config, ConfigError, load_config, parse_env

KEY = "kumi_abcd1234_" + "A" * 43


def write_env(tmp_path, text):
    (tmp_path / ".env").write_text(text, encoding="utf-8")


def test_parse_env_handles_comments_and_quotes():
    assert parse_env('# x\nA=1\n\nB="two words"\nC = \'3\'\n') == {"A": "1", "B": "two words", "C": "3"}


def test_load_config(tmp_path):
    write_env(tmp_path, f"KUMI_API_URL=https://api.example.org/\nKUMI_READER_KEY={KEY}\n")
    config = load_config(tmp_path, environ={})
    assert config == Config("https://api.example.org", KEY)
    assert KEY not in repr(config)


def test_environment_overrides_file(tmp_path):
    write_env(tmp_path, f"KUMI_API_URL=https://a.example.org\nKUMI_READER_KEY={KEY}\n")
    config = load_config(tmp_path, environ={"KUMI_API_URL": "http://localhost:3000"})
    assert config.api_url == "http://localhost:3000"


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ("", "找不到設定"),
        (f"KUMI_API_URL=http://api.example.org\nKUMI_READER_KEY={KEY}", "https://"),
        ("KUMI_API_URL=https://api.example.org\nKUMI_READER_KEY=kumi_short", "格式不正確"),
    ],
)
def test_invalid_config(tmp_path, env, message):
    write_env(tmp_path, env)
    with pytest.raises(ConfigError, match=message) as info:
        load_config(tmp_path, environ={})
    assert KEY not in str(info.value)
