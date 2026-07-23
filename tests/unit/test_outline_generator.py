from __future__ import annotations

import io
import json
import urllib.error
from copy import deepcopy
from pathlib import Path

import pytest

import outline_generator.generate_outline as generator
from document_intelligence.models import IntelligenceChunk


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


def test_build_request_uses_siliconflow_thinking_budget_for_non_v4_flash():
    request = generator.build_request(
        [{"role": "user", "content": "{}"}],
        model="deepseek-ai/DeepSeek-V3.2",
        max_tokens=1000,
        thinking="enabled",
        reasoning_effort="high",
        api_provider="siliconflow",
    )

    assert request["enable_thinking"] is True
    assert request["thinking_budget"] == 16384
    assert "thinking" not in request
    assert "reasoning_effort" not in request


@pytest.mark.parametrize(
    ("requested_effort", "expected_effort"),
    [("low", "high"), ("medium", "high"), ("high", "high"), ("max", "max")],
)
def test_build_request_uses_reasoning_effort_for_siliconflow_v4_flash(
    requested_effort, expected_effort
):
    request = generator.build_request(
        [{"role": "user", "content": "{}"}],
        model="deepseek-ai/DeepSeek-V4-Flash",
        max_tokens=1000,
        thinking="enabled",
        reasoning_effort=requested_effort,
        api_provider="siliconflow",
    )

    assert request["enable_thinking"] is True
    assert request["reasoning_effort"] == expected_effort
    assert "thinking_budget" not in request


def test_build_request_disables_siliconflow_thinking_without_budget():
    request = generator.build_request(
        [{"role": "user", "content": "{}"}],
        model="deepseek-ai/DeepSeek-V3.2",
        max_tokens=1000,
        thinking="disabled",
        reasoning_effort="low",
        api_provider="siliconflow",
    )

    assert request["enable_thinking"] is False
    assert "thinking_budget" not in request


def test_resolve_api_provider_detects_siliconflow_base_url():
    assert (
        generator.resolve_api_provider("auto", "https://api.siliconflow.cn/v1")
        == "siliconflow"
    )


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


def test_call_deepseek_marks_read_timeout_retryable(monkeypatch):
    def fail(request, timeout):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(generator.urllib.request, "urlopen", fail)

    with pytest.raises(generator.DeepSeekAPIError) as caught:
        generator.call_deepseek(
            {"model": "test", "messages": []},
            api_key="secret",
            base_url="https://api.example.test",
            timeout=10,
        )

    assert caught.value.retryable is True
    assert "10 seconds" in str(caught.value)


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


def test_context_compression_memory_is_runtime_only_and_evidence_bound(monkeypatch):
    chunk = IntelligenceChunk(
        id="chunk-0001",
        ordinal=1,
        section_id="sec-1",
        section_path=("sec-1",),
        block_ids=("p001-b001",),
        table_ids=(),
        figure_ids=(),
        payload={
            "chunk_id": "chunk-0001",
            "allowed_evidence_refs": [{"kind": "block", "id": "p001-b001"}],
            "blocks": [{"id": "p001-b001", "text_raw": "原始事实"}],
        },
    )
    content = json.dumps(
        {
            "chunk_id": "model-rewrote-this-id",
            "section_ref": "model-rewrote-this-section",
            "source_ref": "model-added-source",
            "page_id": "model-added-page",
            "summary": "Runtime summary",
            "key_points": ["First key point"],
            "important_insights": ["Important insight"],
        }
    )
    monkeypatch.setattr(generator, "call_deepseek", lambda *args, **kwargs: api_response(content))

    memories = generator.generate_context_memories(
        [chunk],
        api_key="secret",
        base_url="https://api.example.test",
        timeout=10,
        model="test",
        max_tokens=1000,
        thinking="disabled",
        reasoning_effort="low",
        max_attempts=1,
    )

    assert memories[0]["chunk_id"] == "chunk-0001"
    assert memories[0]["section_ref"] == "sec-1"
    assert memories[0]["summary"] == "Runtime summary"
    assert memories[0]["key_points"] == ["First key point"]
    assert memories[0]["important_insights"] == ["Important insight"]
    assert memories[0]["evidence_refs"] == [
        {"kind": "block", "id": "p001-b001"}
    ]
    assert "source_ref" not in memories[0]
    assert "page_id" not in memories[0]


def test_context_compression_prompt_delegates_only_semantic_fields():
    chunk = IntelligenceChunk(
        id="chunk-0001",
        ordinal=1,
        section_id="sec-001",
        section_path=("sec-001",),
        block_ids=("p001-b001",),
        table_ids=(),
        figure_ids=(),
        payload={
            "chunk_id": "chunk-0001",
            "allowed_evidence_refs": [{"kind": "block", "id": "p001-b001"}],
            "blocks": [{"id": "p001-b001", "text_raw": "Source fact"}],
        },
    )

    messages = generator.build_context_compression_messages(chunk)
    payload = json.loads(messages[1]["content"])

    assert set(payload["output_contract"]) == {
        "summary",
        "key_points",
        "important_insights",
    }
    system = messages[0]["content"]
    for prohibited in (
        "chunk_id",
        "section_id",
        "section_ref",
        "source_ref",
        "page_id",
        "evidence_refs",
    ):
        assert prohibited in system


def test_context_compression_corrects_missing_summary(monkeypatch):
    chunk = IntelligenceChunk(
        id="chunk-0002",
        ordinal=2,
        section_id="sec-002",
        section_path=("sec-002",),
        block_ids=("p002-b001",),
        table_ids=(),
        figure_ids=(),
        payload={
            "chunk_id": "chunk-0002",
            "allowed_evidence_refs": [{"kind": "block", "id": "p002-b001"}],
            "blocks": [{"id": "p002-b001", "text_raw": "Source fact"}],
        },
    )
    invalid = json.dumps({"key_points": ["A point"], "important_insights": []})
    valid = json.dumps(
        {
            "summary": "Corrected summary",
            "key_points": ["A point"],
            "important_insights": [],
        }
    )
    responses = iter([api_response(invalid), api_response(valid)])
    requests = []

    def fake_call(request_body, **kwargs):
        requests.append(request_body)
        return next(responses)

    monkeypatch.setattr(generator, "call_deepseek", fake_call)

    memories = generator.generate_context_memories(
        [chunk],
        api_key="secret",
        base_url="https://api.example.test",
        timeout=10,
        model="test",
        max_tokens=1000,
        thinking="disabled",
        reasoning_effort="low",
        max_attempts=2,
    )

    assert memories[0]["chunk_id"] == "chunk-0002"
    assert len(requests[1]["messages"]) == 4
    correction = json.loads(requests[1]["messages"][-1]["content"])
    assert correction["error"] == (
        "Context Compression output must contain a non-empty summary"
    )
    assert "required_chunk_id" not in correction
    assert "required_section_ref" not in correction


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


def test_validate_json_instance_rejects_invalid_document_bundle():
    bundle_schema = json.loads(
        (PROJECT_ROOT / "schemas" / "document_bundle.schema.json").read_text(
            encoding="utf-8"
        )
    )

    with pytest.raises(generator.OutlineGenerationError) as caught:
        generator.validate_json_instance(
            {"schema_version": "1.0"},
            bundle_schema,
            label="DocumentBundle",
        )

    assert "failed schema validation" in str(caught.value)


def test_outline_prompt_requires_verbatim_source_titles_and_topic_sentences():
    prompt = (PROJECT_ROOT / "prompts" / "outline_system_prompt.md").read_text(
        encoding="utf-8"
    )

    assert "title` 不得使用结论式标题" in prompt
    assert "必须逐字使用 `section_catalog` 中该章节的原始 `title`" in prompt
    assert "第一句明确的主旨句" in prompt
    assert "提取重点" in prompt
    assert "中电科普天科技股份有限公司是中国电子科技集团有限公司控制的国有控股上市企业" in prompt
    assert "公网通信业务，包括通信信息技术服务、通信网络产品等业务。" in prompt
    assert "不得输出由关键词机械拼接而成的残句" in prompt


def test_outline_prompt_declares_case_priority_and_source_authority():
    prompt = (PROJECT_ROOT / "prompts" / "outline_system_prompt.md").read_text(
        encoding="utf-8"
    )

    assert "# 指令优先级" in prompt
    assert "Selected few-shot cases" in prompt
    assert "不能覆盖真实证据" in prompt
    assert "不得复制 case 中未出现在当前证据里的" in prompt


def test_default_cli_uses_case_directory_and_accepts_trace_output():
    args = generator.parse_args(["input"])

    assert args.few_shot == PROJECT_ROOT / "prompts" / "outline_cases"
    traced = generator.parse_args(
        ["input", "--case-trace-output", "selected_cases.json"]
    )
    assert traced.case_trace_output == Path("selected_cases.json")
