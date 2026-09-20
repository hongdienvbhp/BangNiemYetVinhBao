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


if __name__ == "__main__":
    unittest.main()
