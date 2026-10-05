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
