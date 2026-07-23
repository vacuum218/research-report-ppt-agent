from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from document_bundle.errors import RawArtifactError, UnsafeArchiveError
from document_bundle.parser.artifacts import map_raw_artifacts, safe_extract_zip


class ArtifactTests(unittest.TestCase):
    def create_complete_result(self, root: Path, *, middle: bool = False) -> dict[str, bytes]:
        payloads = {
            "full.md": "原始 Markdown ![](images/a.png)".encode(),
            "sample_model.json": b'{"model": true}',
            "sample_content_list.json": b'[{"type": "text"}]',
            ("sample_middle.json" if middle else "layout.json"): b'{"layout": true}',
        }
        nested = root / "result"
        nested.mkdir(parents=True)
        for name, content in payloads.items():
            (nested / name).write_bytes(content)
        return payloads

    def test_zip_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("../escaped.txt", "bad")
            with self.assertRaises(UnsafeArchiveError):
                safe_extract_zip(archive, root / "extract")
            self.assertFalse((root / "escaped.txt").exists())

    def test_four_raw_files_are_mapped_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extracted = root / "extracted"
            payloads = self.create_complete_result(extracted, middle=True)
            raw = root / "raw"
            mapped = map_raw_artifacts(extracted, raw)
            self.assertEqual(set(mapped), {"document.md", "model.json", "content_list.json", "layout.json"})
            self.assertEqual((raw / "document.md").read_bytes(), payloads["full.md"])
            self.assertEqual((raw / "model.json").read_bytes(), payloads["sample_model.json"])
            self.assertEqual(
                (raw / "content_list.json").read_bytes(),
                payloads["sample_content_list.json"],
            )
            self.assertEqual(
                (raw / "layout.json").read_bytes(), payloads["sample_middle.json"]
            )

    def test_missing_raw_file_is_strict_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_complete_result(root)
            next(root.rglob("*_model.json")).unlink()
            with self.assertRaisesRegex(RawArtifactError, "Missing.*model"):
                map_raw_artifacts(root, root / "raw")
            self.assertFalse((root / "raw").exists())

    def test_multiple_candidates_are_strict_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_complete_result(root)
            (root / "second_model.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RawArtifactError, "Multiple candidates") as caught:
                map_raw_artifacts(root, root / "raw")
            self.assertIn("sample_model.json", str(caught.exception))
            self.assertIn("second_model.json", str(caught.exception))

    def test_content_list_v2_cannot_replace_content_list(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_complete_result(root)
            content = next(root.rglob("*_content_list.json"))
            content.rename(content.with_name("sample_content_list_v2.json"))
            with self.assertRaisesRegex(RawArtifactError, "Missing.*content_list"):
                map_raw_artifacts(root, root / "raw")

    def test_empty_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_complete_result(root)
            next(root.rglob("full.md")).write_bytes(b"")
            with self.assertRaisesRegex(RawArtifactError, "empty"):
                map_raw_artifacts(root, root / "raw")


if __name__ == "__main__":
    unittest.main()

