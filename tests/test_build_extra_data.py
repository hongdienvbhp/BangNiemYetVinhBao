import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_extra_data as bed  # noqa: E402


class ExtraDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = bed.OUTPUT.read_text(encoding="utf-8")
        marker = "Object.assign(window.TTHC_EXTRA || {}, "
        cls.data = json.loads(text[text.index(marker) + len(marker): text.rindex(");")])
        cls.registry = json.loads(bed.FEES.read_text(encoding="utf-8"))

    def test_generated_file_is_up_to_date(self):
        city_as_of = json.loads(bed.CITY.read_text(encoding="utf-8"))["asOf"]
        self.assertEqual(bed.OUTPUT.read_text(encoding="utf-8"), bed.render(city_as_of))

    def test_nq23_is_current_and_first(self):
        first = self.data["phiLePhi"]["nghiQuyetHP"][0]
        self.assertEqual(first["so"], "23/2026/NQ-HĐND")
        self.assertTrue(first["trangThai"].startswith("Đang áp dụng"))
        self.assertIn("08/8/2026", first["trangThai"])

    def test_expired_resolutions_not_listed_as_current(self):
        for card in self.data["phiLePhi"]["nghiQuyetHP"]:
            if card["so"] in {"07/2025/NQ-HĐND", "08/2025/NQ-HĐND", "17/2024/NQ-HĐND"}:
                self.assertFalse(card["trangThai"].startswith("Đang áp dụng"), card["so"])
                self.assertEqual(card["nhom"], "het_hieu_luc")

    def test_nq23_covers_eleven_zero_dong_items(self):
        nq23 = next(d for d in self.registry["documents"] if d["id"] == "NQ-23-2026")
        self.assertEqual(len(nq23["mienPhiTrucTuyen"]["lePhi"]), 4)
        self.assertEqual(len(nq23["mienPhiTrucTuyen"]["phi"]), 7)
        group = self.data["phiLePhi"]["mucThamKhao"][0]
        self.assertEqual(len(group["muc"]), 11)
        self.assertTrue(all(m["muc"] == "0 đồng" for m in group["muc"]))

    def test_unverified_documents_never_claim_primary_verification(self):
        for doc in self.registry["documents"]:
            if doc["verification"] == "primary_text_read":
                self.assertTrue(any(s.get("sha256") or s["role"] == "cited_by" for s in doc["sources"]), doc["id"])

    def test_decisions_are_unique_and_sorted_desc(self):
        nos = [d["so"] for d in self.data["quyetDinhCongBo"]]
        self.assertEqual(len(nos), len(set(nos)))
        self.assertIn("3433/QĐ-UBND", nos)
        self.assertIn("4016/QĐ-UBND", nos)

    def test_future_effective_decision_flagged(self):
        d = next(x for x in self.data["quyetDinhCongBo"] if x["so"] == "3501/QĐ-UBND")
        self.assertTrue(d["trangThai"].startswith("Chưa có hiệu lực"))

    def test_no_artifact_decision_numbers_in_groups(self):
        text = json.dumps(self.data["quyetDinhTheoTTHC"], ensure_ascii=False)
        self.assertNotIn("2628/QĐ-UBND", text)
        self.assertNotIn("2026/QĐ-UBND", text)


if __name__ == "__main__":
    unittest.main()
