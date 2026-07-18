from __future__ import annotations

import io
import json
import urllib.error
from copy import deepcopy
from pathlib import Path

import pytest

import outline_generator.generate_outline as generator


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")


def api_response(content, *, finish_reason="stop"):
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"content": content},
            }
        ]
    }


@pytest.fixture
def valid_outline():
    return json.loads(
        (PROJECT_ROOT / "examples" / "slide_outline_valid.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture
def outline_schema():
    return json.loads(
        (PROJECT_ROOT / "schemas" / "slide_outline.schema.json").read_text(
            encoding="utf-8"
        )
    )


def test_call_deepseek_returns_decoded_response(monkeypatch):
    expected = api_response('{"schema_version":"1.0.0"}')
    monkeypatch.setattr(
        generator.urllib.request,
        "urlopen",
        lambda request, timeout: FakeHTTPResponse(expected),
    )

    result = generator.call_deepseek(
        {"model": "test", "messages": []},
        api_key="secret",
        base_url="https://api.example.test/",
        timeout=10,
    )

    assert result == expected


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [(401, False), (403, False), (429, True), (500, True)],
)
def test_call_deepseek_classifies_http_errors(
    monkeypatch, status_code, retryable
):
    def fail(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            status_code,
            "failure",
            {},
            io.BytesIO(b'{"error":"failure"}'),
        )

    monkeypatch.setattr(generator.urllib.request, "urlopen", fail)

    with pytest.raises(generator.DeepSeekAPIError) as caught:
        generator.call_deepseek(
            {"model": "test", "messages": []},
            api_key="secret",
            base_url="https://api.example.test",
            timeout=10,
        )

    assert caught.value.status_code == status_code
    assert caught.value.retryable is retryable


def test_call_deepseek_marks_network_failure_retryable(monkeypatch):
    def fail(request, timeout):
        raise urllib.error.URLError("temporary DNS failure")

    monkeypatch.setattr(generator.urllib.request, "urlopen", fail)

    with pytest.raises(generator.DeepSeekAPIError) as caught:
        generator.call_deepseek(
            {"model": "test", "messages": []},
            api_key="secret",
            base_url="https://api.example.test",
            timeout=10,
        )

    assert caught.value.retryable is True


def test_call_deepseek_marks_invalid_api_json_retryable(monkeypatch):
    monkeypatch.setattr(
        generator.urllib.request,
        "urlopen",
        lambda request, timeout: FakeHTTPResponse(b"{not-json}"),
    )

    with pytest.raises(generator.DeepSeekAPIError) as caught:
        generator.call_deepseek(
            {"model": "test", "messages": []},
            api_key="secret",
            base_url="https://api.example.test",
            timeout=10,
        )

    assert caught.value.retryable is True


def test_extract_outline_accepts_valid_json_object(valid_outline):
    result = generator.extract_outline(
        api_response(json.dumps(valid_outline, ensure_ascii=False))
    )

    assert result == valid_outline


def test_extract_outline_rejects_empty_content():
    with pytest.raises(generator.OutlineResponseError) as caught:
        generator.extract_outline(api_response(""))

    assert caught.value.retryable is True


def test_extract_outline_rejects_truncated_output():
    with pytest.raises(generator.OutlineResponseError) as caught:
        generator.extract_outline(
            api_response('{"slides":[', finish_reason="length")
        )

    assert caught.value.retryable is False
    assert "increase --max-tokens" in str(caught.value)


def test_extract_outline_rejects_invalid_json():
    with pytest.raises(generator.OutlineResponseError) as caught:
        generator.extract_outline(api_response("{not-json}"))

    assert caught.value.retryable is True


def test_generate_with_retries_corrects_schema_and_source_errors(
    monkeypatch, valid_outline, outline_schema
):
    invalid = deepcopy(valid_outline)
    invalid["slides"][1]["source_refs"] = ["src_missing"]
    responses = iter(
        [
            api_response(json.dumps(invalid, ensure_ascii=False)),
            api_response(json.dumps(valid_outline, ensure_ascii=False)),
        ]
    )
    requests = []

    def fake_call(request_body, **kwargs):
        requests.append(request_body)
        return next(responses)

    monkeypatch.setattr(generator, "call_deepseek", fake_call)

    outline, issues, attempts = generator.generate_with_retries(
        [{"role": "system", "content": "json"}, {"role": "user", "content": "{}"}],
        outline_schema,
        api_key="secret",
        base_url="https://api.example.test",
        timeout=10,
        model="test",
        max_tokens=1000,
        thinking="disabled",
        reasoning_effort="low",
        max_attempts=2,
    )

    assert outline == valid_outline
    assert issues == []
    assert attempts == 2
    assert len(requests) == 2
    assert len(requests[1]["messages"]) == 4
    assert "SOURCE.UNKNOWN_REFERENCE" in requests[1]["messages"][-1]["content"]


def test_generate_with_retries_recovers_from_empty_content(
    monkeypatch, valid_outline, outline_schema
):
    responses = iter(
        [
            api_response(""),
            api_response(json.dumps(valid_outline, ensure_ascii=False)),
        ]
    )
    requests = []

    def fake_call(request_body, **kwargs):
        requests.append(request_body)
        return next(responses)

    monkeypatch.setattr(generator, "call_deepseek", fake_call)

    outline, issues, attempts = generator.generate_with_retries(
        [{"role": "system", "content": "json"}, {"role": "user", "content": "{}"}],
        outline_schema,
        api_key="secret",
        base_url="https://api.example.test",
        timeout=10,
        model="test",
        max_tokens=1000,
        thinking="disabled",
        reasoning_effort="low",
        max_attempts=2,
    )

    assert outline == valid_outline
    assert issues == []
    assert attempts == 2
    assert "empty content" in requests[1]["messages"][-1]["content"]


def test_generate_with_retries_does_not_retry_auth_failure(
    monkeypatch, outline_schema
):
    calls = 0

    def fake_call(request_body, **kwargs):
        nonlocal calls
        calls += 1
        raise generator.DeepSeekAPIError(
            "unauthorized",
            retryable=False,
            status_code=401,
        )

    monkeypatch.setattr(generator, "call_deepseek", fake_call)

    with pytest.raises(generator.DeepSeekAPIError):
        generator.generate_with_retries(
            [{"role": "system", "content": "json"}],
            outline_schema,
            api_key="secret",
            base_url="https://api.example.test",
            timeout=10,
            model="test",
            max_tokens=1000,
            thinking="disabled",
            reasoning_effort="low",
            max_attempts=2,
        )

    assert calls == 1


def test_validate_json_instance_rejects_invalid_parsed_document():
    parsed_schema = json.loads(
        (PROJECT_ROOT / "schemas" / "parsed_document.schema.json").read_text(
            encoding="utf-8"
        )
    )

    with pytest.raises(generator.OutlineGenerationError) as caught:
        generator.validate_json_instance(
            {"schema_version": "1.0"},
            parsed_schema,
            label="Parsed document",
        )

    assert "failed schema validation" in str(caught.value)
