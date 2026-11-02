import json

import httpx
import pytest

from rfpx.llm import LLMUnavailable, LocalLLM, SchemaUnsupported, assert_local, strip_think


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def models_response(*ids):
    return httpx.Response(200, json={"data": [{"id": i} for i in ids]})


def test_assert_local_accepts_this_machine_and_refuses_everything_else():
    assert assert_local("http://127.0.0.1:1234/v1/") == "http://127.0.0.1:1234/v1"
    assert assert_local("http://localhost:1234/v1") == "http://localhost:1234/v1"
    for bad in ("https://api.openai.com/v1", "http://192.168.1.20:1234/v1", "http://example.com/v1"):
        with pytest.raises(ValueError, match="non-local"):
            assert_local(bad)
    with pytest.raises(ValueError, match="scheme"):
        assert_local("ftp://127.0.0.1/v1")


def test_the_client_cannot_be_pointed_at_a_remote_host():
    with pytest.raises(ValueError):
        LocalLLM("https://api.openai.com/v1")


def test_strip_think_removes_reasoning_blocks():
    assert strip_think("<think>hmm\nmore</think>\n{\"questions\": []}") == '{"questions": []}'
    assert strip_think("{\"a\": 1}") == '{"a": 1}'
    assert strip_think("only the tail </think> {\"a\": 1}") == '{"a": 1}'


def test_model_choice_prefers_the_override_then_the_small_default_and_skips_embedding_models(monkeypatch):
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        return models_response("text-embedding-nomic-embed-text-v1.5", "qwen/qwen3.8-27b", "qwen2.5-3b-instruct")

    monkeypatch.delenv("LLM_CHAT_MODEL", raising=False)
    assert LocalLLM(client=client(handler)).model() == "qwen2.5-3b-instruct"
    monkeypatch.setenv("LLM_CHAT_MODEL", "qwen/qwen3.8-27b")
    assert LocalLLM(client=client(handler)).model() == "qwen/qwen3.8-27b"
    assert LocalLLM(model="qwen2.5-3b-instruct", client=client(handler)).model() == "qwen2.5-3b-instruct"
    assert seen["path"] == "/v1/models"


def test_chat_sends_a_schema_and_returns_the_message_text():
    sent = {}

    def handler(request):
        if request.url.path.endswith("/models"):
            return models_response("qwen2.5-3b-instruct")
        sent.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"questions": []}'}}]})

    llm = LocalLLM(client=client(handler))
    out = llm.chat([{"role": "user", "content": "hi"}], max_tokens=50, schema={"type": "object"})
    assert out == '{"questions": []}'
    assert sent["response_format"]["type"] == "json_schema" and sent["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert sent["temperature"] == 0 and sent["max_tokens"] == 50 and sent["messages"][-1]["content"] == "hi"


def test_reasoning_models_get_the_no_think_switch_on_the_last_user_message_only():
    sent = {}

    def handler(request):
        if request.url.path.endswith("/models"):
            return models_response("qwen/qwen3.8-27b")
        sent.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "<think>x</think>ok"}}]})

    llm = LocalLLM(client=client(handler))
    assert llm.chat([{"role": "system", "content": "s"}, {"role": "user", "content": "a"}, {"role": "assistant", "content": "b"},
                     {"role": "user", "content": "c"}]) == "ok"
    contents = [m["content"] for m in sent["messages"]]
    assert contents == ["s", "a", "b", "c /no_think"]


def test_a_server_that_rejects_the_schema_raises_a_specific_error():
    def handler(request):
        if request.url.path.endswith("/models"):
            return models_response("qwen2.5-3b-instruct")
        return httpx.Response(400, json={"error": "response_format.type must be json_schema or text"})

    with pytest.raises(SchemaUnsupported):
        LocalLLM(client=client(handler)).chat([{"role": "user", "content": "x"}], schema={"type": "object"})
    with pytest.raises(LLMUnavailable) as err:
        LocalLLM(client=client(handler)).chat([{"role": "user", "content": "x"}])
    assert not isinstance(err.value, SchemaUnsupported)


def test_an_unreachable_server_or_an_empty_reply_is_llm_unavailable():
    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMUnavailable, match="not reachable"):
        LocalLLM(client=client(down)).model()

    def empty(request):
        if request.url.path.endswith("/models"):
            return models_response("qwen2.5-3b-instruct")
        return httpx.Response(200, json={"choices": [{"message": {"content": "<think>only thoughts</think>"}}]})

    with pytest.raises(LLMUnavailable, match="empty"):
        LocalLLM(client=client(empty)).chat([{"role": "user", "content": "x"}])


def test_the_environment_switch_turns_every_call_off(monkeypatch):
    monkeypatch.setenv("RFPX_NO_LLM", "1")
    with pytest.raises(LLMUnavailable, match="disabled"):
        LocalLLM(client=client(lambda r: models_response("x"))).model()


def test_status_reports_endpoint_model_and_reason():
    ok = LocalLLM(client=client(lambda r: models_response("qwen2.5-3b-instruct"))).status()
    assert ok["ready"] and ok["model"] == "qwen2.5-3b-instruct" and ok["endpoint"] == "http://127.0.0.1:1234/v1"

    def down(request):
        raise httpx.ConnectError("refused")

    bad = LocalLLM(client=client(down)).status()
    assert not bad["ready"] and "not reachable" in bad["reason"]
