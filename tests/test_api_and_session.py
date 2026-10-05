import uuid

import pytest
import responses

from kumi_reader.api import ApiError, KumiApi
from kumi_reader.instance import load_or_create_instance_id
from kumi_reader.outbox import Outbox
from kumi_reader.session import start_session

URL = "https://api.example.org"
KEY = "kumi_abcd1234_" + "A" * 43
INSTANCE = "11111111-1111-4111-8111-111111111111"
WHOAMI = {"keyName": "辦公室電腦", "holderDiscordId": "1" * 18, "program": "members", "boundAt": "2026-10-05T00:00:00.000Z"}


def make_root(tmp_path):
    (tmp_path / ".env").write_text(f"KUMI_API_URL={URL}\nKUMI_READER_KEY={KEY}\n", encoding="utf-8")
    return tmp_path


@responses.activate
def test_requests_carry_key_program_and_instance():
    responses.get(f"{URL}/api/reader/whoami", json=WHOAMI)
    me = KumiApi(URL, KEY, "members", INSTANCE).whoami()
    assert me.key_name == "辦公室電腦"
    headers = responses.calls[0].request.headers
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert headers["X-Kumi-Program"] == "members"
    assert headers["X-Kumi-Instance"] == INSTANCE


@responses.activate
def test_api_errors_use_backend_message():
    responses.post(
        f"{URL}/api/reader/member-batches",
        status=422,
        json={"code": "VALIDATION_FAILED", "message": "欄位格式錯誤", "fields": {"members.0.uid": "UID 必須是 12 碼數字"}},
    )
    with pytest.raises(ApiError) as info:
        KumiApi(URL, KEY, "members", INSTANCE).upload_member_batch({})
    err = info.value
    assert (err.status, err.code, err.retryable) == (422, "VALIDATION_FAILED", False)
    assert err.describe() == "欄位格式錯誤（members.0.uid：UID 必須是 12 碼數字）"
    assert KEY not in err.describe()


def test_network_error_is_retryable():
    with pytest.raises(ApiError) as info:
        KumiApi("http://127.0.0.1:9", KEY, "members", INSTANCE, timeout=0.5).whoami()
    assert info.value.status == 0
    assert info.value.retryable


def test_instance_id_is_created_once(tmp_path):
    first = load_or_create_instance_id(tmp_path)
    assert str(uuid.UUID(first)) == first
    assert load_or_create_instance_id(tmp_path) == first
    (tmp_path / "instance-id").write_text("broken", encoding="utf-8")
    assert load_or_create_instance_id(tmp_path) != first


def test_outbox_flush_keeps_order_and_stops_on_retryable(tmp_path):
    box = Outbox(tmp_path)
    for i in range(3):
        box.save("member-batch", {"n": i})
    sent = []

    def send(kind, body):
        if body["n"] == 1:
            raise ApiError(0, "NETWORK", "連不上")
        sent.append(body["n"])

    assert box.flush(send) == (1, 2)
    assert sent == [0]
    assert len(box.pending()) == 2


def test_outbox_moves_unretryable_to_failed(tmp_path):
    box = Outbox(tmp_path)
    box.save("member-batch", {"n": 0})
    box.save("member-batch", {"n": 1})

    def send(kind, body):
        if body["n"] == 0:
            raise ApiError(422, "VALIDATION_FAILED", "欄位格式錯誤")

    assert box.flush(send) == (1, 0)
    assert len(list((tmp_path / "outbox" / "failed").glob("*.json"))) == 1


@responses.activate
def test_start_session_flushes_outbox(tmp_path, capsys):
    root = make_root(tmp_path)
    Outbox(root / "data").save("member-batch", {"status": "complete", "expectedCount": 0, "members": []})
    responses.get(f"{URL}/api/reader/whoami", json=WHOAMI)
    responses.post(f"{URL}/api/reader/member-batches", json={"batchId": 1})
    session = start_session("members", root)
    assert session is not None
    assert session.outbox.pending() == []
    out = capsys.readouterr().out
    assert "success:已重送先前未上傳成功的結果 1 筆。" in out
    assert KEY not in out


@responses.activate
def test_start_session_reports_bound_key(tmp_path, capsys):
    root = make_root(tmp_path)
    responses.get(
        f"{URL}/api/reader/whoami",
        status=403,
        json={"code": "READER_KEY_BOUND", "message": "這把金鑰已綁定另一份家族成員讀取程式。"},
    )
    assert start_session("members", root) is None
    assert "err:這把金鑰已綁定另一份家族成員讀取程式。" in capsys.readouterr().out


def test_start_session_without_config(tmp_path, capsys):
    assert start_session("members", tmp_path) is None
    assert "err:找不到設定" in capsys.readouterr().out
