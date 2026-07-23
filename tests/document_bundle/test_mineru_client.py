from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from document_bundle.config import MinerUConfig
from document_bundle.errors import (
    MinerUConfigurationError,
    MinerUError,
    MinerUTimeoutError,
)
from document_bundle.parser.mineru_client import MinerUClient


TOKEN = "unit-test-secret-token"


def json_response(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


class MinerUClientTests(unittest.TestCase):
    def make_client(
        self,
        api_handler,
        transfer_handler=None,
        *,
        config: MinerUConfig | None = None,
        monotonic_fn=None,
    ) -> MinerUClient:
        if transfer_handler is None:
            transfer_handler = lambda request: httpx.Response(200)
        client = MinerUClient(
            config=config or MinerUConfig(max_retries=0, poll_interval_seconds=0),
            token=TOKEN,
            api_transport=httpx.MockTransport(api_handler),
            transfer_transport=httpx.MockTransport(transfer_handler),
            sleep_fn=lambda _: None,
            monotonic_fn=monotonic_fn or (lambda: 0.0),
        )
        self.addCleanup(client.close)
        return client

    def test_environment_variable_is_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                MinerUConfigurationError, "MINERU_API_TOKEN is not configured"
            ):
                MinerUClient()

    def test_request_upload_url_uses_fixed_payload(self) -> None:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return json_response(
                {
                    "code": 0,
                    "trace_id": "trace-1",
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.invalid/signed?secret=1"],
                    },
                }
            )

        client = self.make_client(handler)
        result = client.request_upload_url(Path("sample.pdf"), "data-1")
        self.assertEqual(
            result, ("batch-1", "https://upload.invalid/signed?secret=1", "trace-1")
        )
        request = seen[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url.path, "/api/v4/file-urls/batch")
        self.assertEqual(request.headers["authorization"], f"Bearer {TOKEN}")
        self.assertEqual(request.headers["content-type"], "application/json")
        body = json.loads(request.content)
        self.assertEqual(
            body,
            {
                "files": [
                    {"name": "sample.pdf", "data_id": "data-1", "is_ocr": False}
                ],
                "model_version": "vlm",
                "language": "ch",
                "enable_table": True,
                "enable_formula": True,
            },
        )
        self.assertNotIn("page_ranges", body)
        self.assertNotIn("extra_formats", body)

    def test_http_success_with_nonzero_mineru_code_fails(self) -> None:
        client = self.make_client(
            lambda request: json_response(
                {"code": 1001, "msg": "rejected", "trace_id": "trace-x"}
            )
        )
        with self.assertRaises(MinerUError) as caught:
            client.request_upload_url(Path("sample.pdf"), "data-1")
        self.assertEqual(caught.exception.code, 1001)
        self.assertEqual(caught.exception.trace_id, "trace-x")

    def test_signed_upload_failure_has_no_auth_header_or_content_type(self) -> None:
        seen: list[httpx.Request] = []

        def transfer(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            request.read()
            return httpx.Response(500)

        client = self.make_client(lambda request: json_response({}), transfer)
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "sample.pdf"
            pdf.write_bytes(b"%PDF-test")
            with self.assertRaises(MinerUError) as caught:
                client.upload_pdf(pdf, "https://upload.invalid/private-query", "batch-1")
        self.assertEqual(caught.exception.http_status, 500)
        self.assertEqual(caught.exception.batch_id, "batch-1")
        self.assertNotIn("authorization", seen[0].headers)
        self.assertNotIn("content-type", seen[0].headers)
        self.assertNotIn("private-query", str(caught.exception))

    def test_upload_retry_restarts_from_first_byte(self) -> None:
        bodies: list[bytes] = []

        def transfer(request: httpx.Request) -> httpx.Response:
            bodies.append(request.read())
            return httpx.Response(503 if len(bodies) == 1 else 200)

        client = self.make_client(
            lambda request: json_response({}),
            transfer,
            config=MinerUConfig(max_retries=1, poll_interval_seconds=0),
        )
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "sample.pdf"
            pdf.write_bytes(b"complete-pdf-bytes")
            client.upload_pdf(pdf, "https://upload.invalid/signed", "batch-retry")
        self.assertEqual(bodies, [b"complete-pdf-bytes", b"complete-pdf-bytes"])

    def test_poll_waiting_pending_running_done(self) -> None:
        states = iter(["waiting-file", "pending", "running", "done"])

        def handler(request: httpx.Request) -> httpx.Response:
            state = next(states)
            record = {"state": state}
            if state == "done":
                record["full_zip_url"] = "https://download.invalid/signed"
            return json_response(
                {"code": 0, "trace_id": "trace-poll", "data": {"extract_result": [record]}}
            )

        client = self.make_client(handler)
        result = client.poll_result("batch-1", initial_trace_id="trace-submit")
        self.assertEqual(result.batch_id, "batch-1")
        self.assertEqual(result.trace_id, "trace-poll")
        self.assertEqual(result.full_zip_url, "https://download.invalid/signed")

    def test_failed_state_reports_context(self) -> None:
        client = self.make_client(
            lambda request: json_response(
                {
                    "code": 0,
                    "trace_id": "trace-fail",
                    "data": {
                        "extract_result": [
                            {"state": "failed", "err_msg": "conversion failed"}
                        ]
                    },
                }
            )
        )
        with self.assertRaises(MinerUError) as caught:
            client.poll_result("batch-fail")
        error = caught.exception
        self.assertEqual(error.batch_id, "batch-fail")
        self.assertEqual(error.trace_id, "trace-fail")
        self.assertEqual(error.state, "failed")
        self.assertEqual(error.http_status, 200)
        self.assertEqual(error.code, 0)
        self.assertEqual(error.mineru_message, "conversion failed")

    def test_poll_timeout_is_finite(self) -> None:
        clock = iter([0.0, 1.0])
        client = self.make_client(
            lambda request: json_response(
                {
                    "code": 0,
                    "data": {"extract_result": [{"state": "running"}]},
                }
            ),
            config=MinerUConfig(
                max_retries=0,
                poll_interval_seconds=0,
                poll_timeout_seconds=0.5,
            ),
            monotonic_fn=lambda: next(clock),
        )
        with self.assertRaises(MinerUTimeoutError) as caught:
            client.poll_result("batch-timeout")
        self.assertEqual(caught.exception.batch_id, "batch-timeout")
        self.assertEqual(caught.exception.state, "running")

    def test_zip_download_failure_does_not_send_token(self) -> None:
        seen: list[httpx.Request] = []

        def transfer(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(404)

        client = self.make_client(lambda request: json_response({}), transfer)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(MinerUError) as caught:
                client.download_zip(
                    "https://download.invalid/private-query",
                    Path(directory) / "result.zip",
                    "batch-zip",
                )
        self.assertEqual(caught.exception.http_status, 404)
        self.assertEqual(caught.exception.batch_id, "batch-zip")
        self.assertNotIn("authorization", seen[0].headers)
        self.assertNotIn("private-query", str(caught.exception))

    def test_token_is_redacted_from_server_error_and_logs(self) -> None:
        client = self.make_client(
            lambda request: json_response(
                {"code": 9, "msg": f"server echoed {TOKEN}"}
            )
        )
        with self.assertLogs(
            "document_bundle.parser.mineru_client", level="INFO"
        ) as logs:
            # Produce one safe log record before the expected API error.
            import logging

            logging.getLogger(
                "document_bundle.parser.mineru_client"
            ).info("safe operation")
            with self.assertRaises(MinerUError) as caught:
                client.request_upload_url(Path("sample.pdf"), "data-1")
        combined = "\n".join(logs.output) + str(caught.exception)
        self.assertNotIn(TOKEN, combined)
        self.assertIn("[REDACTED]", str(caught.exception))

    def test_server_urls_are_redacted_from_exceptions(self) -> None:
        client = self.make_client(
            lambda request: json_response(
                {"code": 9, "msg": "failed at https://signed.invalid/private?key=secret"}
            )
        )
        with self.assertRaises(MinerUError) as caught:
            client.request_upload_url(Path("sample.pdf"), "data-1")
        message = str(caught.exception)
        self.assertNotIn("signed.invalid", message)
        self.assertIn("[REDACTED_URL]", message)


if __name__ == "__main__":
    unittest.main()
