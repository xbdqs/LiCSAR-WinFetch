from __future__ import annotations

import datetime as dt
import importlib.util
import json
import logging
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import requests


ROOT = Path(__file__).resolve().parents[1]
SOFTWARE = ROOT
sys.path.insert(0, str(SOFTWARE))

import download_licsar_windows as downloader  # noqa: E402
import multiframe_planner as planner  # noqa: E402


def load_runner():
    path = ROOT / "validation" / "paper_validation_runner.py"
    spec = importlib.util.spec_from_file_location("paper_validation_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def response(status: int, url: str, body: bytes = b"", content_type: str = "application/octet-stream") -> requests.Response:
    result = requests.Response()
    result.status_code = status
    result.url = url
    result.headers["Content-Type"] = content_type
    result.headers["Content-Length"] = str(len(body))
    result._content = body
    result._content_consumed = True
    return result


def settings(output: Path) -> downloader.Settings:
    return downloader.Settings(
        frame="124D_04854_171313",
        start=dt.date(2016, 9, 9),
        end=dt.date(2018, 5, 8),
        output_parent=output,
        retries=0,
    )


class MappingClient(downloader.LiCSARClient):
    def __init__(self, config: downloader.Settings, mapping: dict[tuple[str, str], requests.Response]):
        super().__init__(config, logging.getLogger("test.mapping"))
        self.mapping = mapping

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        return self.mapping.get((method, url), response(404, url, b"", "text/plain"))


class ValidationTests(unittest.TestCase):
    def test_frame_date_and_pair_validation(self) -> None:
        self.assertEqual(downloader.validate_frame("021D_04972_131213"), "021D_04972_131213")
        with self.assertRaises(Exception):
            downloader.validate_frame("bad")
        self.assertEqual(downloader.parse_yyyymmdd("20200131"), dt.date(2020, 1, 31))
        with self.assertRaises(Exception):
            downloader.parse_yyyymmdd("20201301")
        self.assertTrue(downloader.PAIR_RE.fullmatch("20200101_20200113"))
        self.assertFalse(downloader.PAIR_RE.fullmatch("20200101-20200113"))

    def test_qilian_inventory_safeguard(self) -> None:
        frames = planner.load_frames(SOFTWARE / "examples" / "qilian_metadata_planning" / "qilianshan_frames.json")
        self.assertEqual(len(frames), 22)
        self.assertEqual(len(set(frames)), 22)
        self.assertEqual(sum(frame[3] == "A" for frame in frames), 11)
        self.assertEqual(sum(frame[3] == "D" for frame in frames), 11)
        self.assertNotIn("172A_05226_111616", frames)
        self.assertIn("172A_05237_161616", frames)

    def test_network_diagnostics(self) -> None:
        connected = planner.network_diagnostics(
            ["20200101", "20200113", "20200125"],
            ["20200101_20200113", "20200113_20200125"],
        )
        self.assertTrue(connected.connected)
        self.assertEqual(connected.component_count, 1)
        disconnected = planner.network_diagnostics(
            ["20200101", "20200113", "20200201"],
            ["20200101_20200113"],
        )
        self.assertFalse(disconnected.connected)
        self.assertEqual(disconnected.isolated_epoch_count, 1)

    def test_common_pair_mode_retains_isolated_common_epochs(self) -> None:
        a = planner.FrameInventory(
            frame="070A_05026_131313",
            direction="Ascending",
            track_group="070A",
            epochs=["20200101", "20200113", "20200125"],
            pairs=["20200101_20200113", "20200113_20200125"],
        )
        b = planner.FrameInventory(
            frame="070A_05251_161617",
            direction="Ascending",
            track_group="070A",
            epochs=["20200101", "20200113", "20200125"],
            pairs=["20200101_20200113"],
        )
        selected_epochs, selected_pairs = planner.selected_for_mode(
            a, "common-pairs", [a, b]
        )
        self.assertEqual(selected_epochs, ["20200101", "20200113", "20200125"])
        diag = planner.network_diagnostics(selected_epochs, selected_pairs)
        self.assertFalse(diag.connected)
        self.assertEqual(diag.isolated_epoch_count, 1)

    def test_single_frame_group_marks_exact_intersection_not_applicable(self) -> None:
        inv = planner.FrameInventory(
            frame="055A_05221_131313",
            direction="Ascending",
            track_group="055A",
            epochs=["20200101", "20200113"],
            pairs=["20200101_20200113"],
        )
        row = planner.summarize_group(
            "055A", "relative-orbit", [inv], "independent", False
        )
        self.assertFalse(row["exact_intersection_applicable"])
        self.assertEqual(row["common_epoch_count"], "")
        self.assertEqual(row["common_pair_count"], "")


class ResolverTests(unittest.TestCase):
    def test_direct_file_and_redirect_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expected = "https://example.test/file.tif"
            final = "https://objects.example.test/file.tif"
            client = MappingClient(settings(Path(tmp)), {
                ("HEAD", expected): response(200, final, b"data"),
            })
            self.assertEqual(client.resolve_file_url(expected), final)

    def test_text_manifest_resolution_without_trailing_slash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expected = "https://example.test/interferograms/20200101_20200113/file.tif"
            container = "https://example.test/interferograms/20200101_20200113"
            target = "https://ceda.example.test/data/file.tif"
            manifest = f'<a href="{target}">file.tif</a>'.encode()
            client = MappingClient(settings(Path(tmp)), {
                ("GET", container): response(200, container, manifest, "text/plain"),
            })
            self.assertEqual(client.resolve_file_url(expected), target)

    def test_plain_text_absolute_url_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expected = "https://example.test/epochs/20200101/20200101.geo.mli.tif"
            container = "https://example.test/epochs/20200101"
            target = "https://ceda.example.test/data/20200101.geo.mli.tif"
            client = MappingClient(settings(Path(tmp)), {
                ("GET", container): response(200, container, target.encode(), "text/plain"),
            })
            self.assertEqual(client.resolve_file_url(expected), target)


class DownloadAndStructureTests(unittest.TestCase):
    def test_part_file_resumes_and_records_transferred_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = settings(Path(tmp))
            client = downloader.LiCSARClient(config, logging.getLogger("test.resume"))
            target = config.geoc_dir / "sample.bin"
            target.parent.mkdir(parents=True)
            part = target.with_name(target.name + ".part")
            part.write_bytes(b"abc")
            payload = b"abcdef"

            with mock.patch.object(client, "remote_info", return_value=(len(payload), None, "https://example.test/sample.bin")), mock.patch.object(
                client,
                "_request",
                return_value=response(206, "https://example.test/sample.bin", b"def"),
            ):
                result = client.download_one(downloader.RemoteFile("unused", target, "metadata", "sample"))

            self.assertEqual(result.status, "downloaded")
            self.assertEqual(result.bytes_transferred, 3)
            self.assertEqual(target.read_bytes(), payload)
            self.assertFalse(part.exists())

    def test_server_ignoring_range_restarts_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = settings(Path(tmp))
            client = downloader.LiCSARClient(config, logging.getLogger("test.restart"))
            target = config.geoc_dir / "sample.bin"
            target.parent.mkdir(parents=True)
            target.with_name(target.name + ".part").write_bytes(b"old")
            payload = b"new-content"
            with mock.patch.object(client, "remote_info", return_value=(len(payload), None, "https://example.test/sample.bin")), mock.patch.object(
                client,
                "_request",
                return_value=response(200, "https://example.test/sample.bin", payload),
            ):
                result = client.download_one(downloader.RemoteFile("unused", target, "metadata", "sample"))
            self.assertEqual(result.status, "downloaded")
            self.assertEqual(result.bytes_transferred, len(payload))
            self.assertEqual(target.read_bytes(), payload)

    def test_unavailable_required_product_is_critical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = settings(Path(tmp))
            pair = config.geoc_dir / "20200101_20200113"
            pair.mkdir(parents=True)
            for suffix in ("unw", "cc"):
                (pair / f"{pair.name}.geo.{suffix}.tif").write_bytes(b"x")
            missing = downloader.Result(
                "unw", "20200113_20200125.geo.unw.tif", "missing", "url",
                "unavailable", 0, "not found",
            )
            critical, warnings = downloader.verify_structure(config, [missing])
            self.assertTrue(any("Required product unavailable" in issue for issue in critical))
            self.assertFalse(any("failed" in warning.lower() for warning in warnings))

    def test_optional_unavailable_product_is_not_critical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = settings(Path(tmp))
            pair = config.geoc_dir / "20200101_20200113"
            pair.mkdir(parents=True)
            for suffix in ("unw", "cc"):
                (pair / f"{pair.name}.geo.{suffix}.tif").write_bytes(b"x")
            optional = downloader.Result("gacos", "optional", "missing", "url", "unavailable", 0, "not found")
            critical, _ = downloader.verify_structure(config, [optional])
            self.assertEqual(critical, [])


class EvidenceSafetyTests(unittest.TestCase):
    def test_zip_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escape.txt", "bad")
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaises(ValueError):
                    runner.safe_extract_zip(archive, root / "extract")

    def test_empty_existing_frame_is_not_run_without_fake_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(runner, "EXISTING_OUT", Path(tmp)):
            result = runner.analyze_existing_frame({"existing_frame_dir": ""})
            self.assertEqual(result["status"], "not_run")
            self.assertNotIn("frame_dir", result)
            saved = json.loads((Path(tmp) / "Existing_Real_Frame_results.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "not_run")

    def test_benchmark_epoch_limit_guard_precedes_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(runner, "BENCHMARK_OUT", Path(tmp)), mock.patch.object(
            runner, "load_downloader_module"
        ) as load_module:
            result = runner.run_benchmark({"benchmark": {"enabled": True, "epoch_limit": 22}})
            self.assertEqual(result["status"], "invalid_config")
            load_module.assert_not_called()


if __name__ == "__main__":
    unittest.main()
