"""Opt-in Windows integration regression: run the real native player, no live CP history.

Set CP_NATIVE_TEST_RUNTIME, CP_NATIVE_TEST_MEDIA_ROOT (containing ascii.mp4,
فيلم.mp4 and مجلد/Les Misérables.mp4), and CP_NATIVE_TEST_LES_MIS.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENABLED = os.name == "nt" and all(os.environ.get(key) for key in (
    "CP_NATIVE_TEST_RUNTIME", "CP_NATIVE_TEST_MEDIA_ROOT", "CP_NATIVE_TEST_LES_MIS",
))


@unittest.skipUnless(ENABLED, "Requires explicit native runtime and isolated media fixtures")
class NativeUnicodePlaybackTests(unittest.TestCase):
    def assert_plays(self, media, *, minimum_duration=1000, screenshot=None, subtitle=None):
        command = [sys.executable, str(ROOT / "native/player/tools/smoke_player.py"),
                   "--runtime", os.environ["CP_NATIVE_TEST_RUNTIME"], "--media", str(media),
                   "--observe-seconds", "4", "--require-min-position-ms", "1000",
                   "--cache-directory-name", "ذاكرة"]
        if screenshot:
            command.extend(["--screenshot", str(screenshot)])
        if subtitle:
            command.extend(["--external-subtitle", str(subtitle), "--require-subtitle"])
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                timeout=55, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["max_duration_ms"], minimum_duration)
        self.assertGreaterEqual(report["max_position_ms"], 1000)
        self.assertGreater(report["audio_tracks"], 0)
        # The player exposes audio/subtitle tracks, not video tracks. Playback
        # progress must advance independently of how many subtitles a file has.
        self.assertGreaterEqual(report["progress_samples"], 2)
        self.assertGreater(report["last_position_ms"], report["first_position_ms"])
        self.assertEqual(report["process_exit_code"], 0)
        report_root = os.environ.get("CP_NATIVE_TEST_REPORT_ROOT")
        if report_root:
            destination = Path(report_root)
            destination.mkdir(parents=True, exist_ok=True)
            (destination / f"{self._testMethodName}.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_real_les_miserables_with_accented_filename(self):
        report_root = os.environ.get("CP_NATIVE_TEST_REPORT_ROOT")
        self.assert_plays(Path(os.environ["CP_NATIVE_TEST_LES_MIS"]),
                          minimum_duration=9_000_000,
                          screenshot=Path(report_root) / "les-miserables.png" if report_root else None)

    def test_arabic_filename(self):
        fixtures = Path(os.environ["CP_NATIVE_TEST_MEDIA_ROOT"])
        report_root = os.environ.get("CP_NATIVE_TEST_REPORT_ROOT")
        self.assert_plays(fixtures / "فيلم.mp4", subtitle=fixtures / "ترجمة.srt",
                          screenshot=Path(report_root) / "arabic-filename.png" if report_root else None)

    def test_arabic_directory_and_accented_filename(self):
        self.assert_plays(Path(os.environ["CP_NATIVE_TEST_MEDIA_ROOT"]) / "مجلد" / "Les Misérables.mp4")

    def test_ascii_filename_remains_playable(self):
        self.assert_plays(Path(os.environ["CP_NATIVE_TEST_MEDIA_ROOT"]) / "ascii.mp4")

    def test_arabic_external_subtitle_on_ascii_video(self):
        fixtures = Path(os.environ["CP_NATIVE_TEST_MEDIA_ROOT"])
        self.assert_plays(fixtures / "ascii.mp4", subtitle=fixtures / "ترجمة.srt")


if __name__ == "__main__":
    unittest.main()
