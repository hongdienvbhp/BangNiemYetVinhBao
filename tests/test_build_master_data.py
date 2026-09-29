from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_master_data", ROOT / "scripts" / "build_master_data.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BuildMasterDataTitleRepairTest(unittest.TestCase):
    def test_removes_bell_delimited_suffix(self) -> None:
        self.assertEqual(
            MODULE.repair_city_name("\x07Tên thủ tục\x07(1) Trong", "9.999999"),
            "Tên thủ tục",
        )

    def test_removes_leading_bell(self) -> None:
        self.assertEqual(
            MODULE.repair_city_name("\x07Tên thủ tục", "9.999999"),
            "Tên thủ tục",
        )


class BuildMasterDataCityRepealTest(unittest.TestCase):
    def _run(self, current_state: str) -> tuple[list[dict], list[dict]]:
        import json
        import tempfile

        payload = {"rows": [{
            "code": "9.999999", "name": "Tên thủ tục", "decisionNo": "1/QĐ-UBND",
            "decisionDate": "2026-05-19", "sectionStatus": "repealed",
            "currentStateAtAsOf": current_state, "levelHint": "commune",
            "communeReceptionEvidence": True, "field": "THỬ",
        }]}
        public = [{"ma": "9.999999", "ten": "Tên thủ tục", "linhVuc": "THỬ"}]
        excluded: list[dict] = []
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "city.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            original = MODULE.CITY_UPDATES
            MODULE.CITY_UPDATES = path
            try:
                MODULE.apply_city_updates(public, excluded, [], {}, {})
            finally:
                MODULE.CITY_UPDATES = original
        return public, excluded

    def test_pending_effective_date_decision_does_not_repeal(self) -> None:
        public, excluded = self._run("reviewed_pending_effective_date")
        self.assertEqual([row["ma"] for row in public], ["9.999999"])
        self.assertEqual(excluded, [])

    def test_effective_decision_repeals(self) -> None:
        public, excluded = self._run("current_or_immediate_unless_repealed")
        self.assertEqual(public, [])
        self.assertEqual(excluded[0]["verificationStatus"], "repealed_by_official_city_decision")


if __name__ == "__main__":
    unittest.main()
