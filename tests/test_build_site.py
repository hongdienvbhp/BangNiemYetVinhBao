import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_site import RUNTIME_FILES, build

ROOT = Path(__file__).resolve().parents[1]


class BuildSiteTests(unittest.TestCase):
    def test_build_copies_only_runtime_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "_site"
            published = build(out)
            self.assertGreater(published, 0)
            files = sorted(
                p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file() and p.name != ".nojekyll"
            )
            self.assertEqual(files, sorted(RUNTIME_FILES))

    def test_firebase_config_serves_build_output(self):
        cfg = json.loads((ROOT / "firebase.json").read_text(encoding="utf-8"))
        hosting = cfg["hosting"]
        self.assertEqual(hosting["public"], "_site")
        sources = {h["source"]: h["headers"] for h in hosting["headers"]}
        sw = {h["key"]: h["value"] for h in sources["/sw.js"]}
        self.assertEqual(sw["Cache-Control"], "no-cache")

    def test_build_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                build(Path(tmp) / "_site", root=Path(tmp))


if __name__ == "__main__":
    unittest.main()
