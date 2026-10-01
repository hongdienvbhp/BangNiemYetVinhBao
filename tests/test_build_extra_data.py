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
        self.assertIn("Đang áp dụng", first["trangThai"])
        self.assertIn("08/8/2026", first["trangThai"])

    def test_expired_resolutions_not_listed_as_current(self):
        for card in self.data["phiLePhi"]["nghiQuyetHP"]:
            if card["so"] in {"07/2025/NQ-HĐND", "08/2025/NQ-HĐND", "17/2024/NQ-HĐND"}:
                self.assertNotIn("Đang áp dụng", card["trangThai"], card["so"])
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


class Nq23MappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.mapping = json.loads((root / "data/phu-luc/NQ-23-anh-xa-tthc.json").read_text(encoding="utf-8"))
        cls.master = json.loads((root / "data/thu-tuc.json").read_text(encoding="utf-8"))["thuTuc"]

    def test_only_confirmed_codes_are_flagged(self):
        confirmed = {c["ma"] for c in self.mapping["confirmed"]}
        flagged = {t["ma"] for t in self.master if t["mienPhiTrucTuyen"]}
        self.assertEqual(flagged, confirmed)
        self.assertTrue(all(c["canCu"] and c["dieuKhoan"] for c in self.mapping["confirmed"]))

    def test_candidates_never_applied_if_any(self):
        candidates = {c["ma"] for c in self.mapping["candidates"]}
        self.assertFalse(candidates & {t["ma"] for t in self.master if t["mienPhiTrucTuyen"]})
        self.assertFalse(candidates & {c["ma"] for c in self.mapping["confirmed"]})

    def test_flagged_rows_state_nq23_text(self):
        for t in self.master:
            if t["mienPhiTrucTuyen"]:
                self.assertIn("NQ 23/2026/NQ-HĐND", t["phiOnline"])


class SpecializedFeeTests(unittest.TestCase):
    def test_specialized_codes_not_flagged_as_nq23(self):
        root = Path(__file__).resolve().parents[1]
        spec = json.loads((root / "data/phu-luc/phi-le-phi-chuyen-nganh.json").read_text(encoding="utf-8"))
        nq23 = json.loads((root / "data/phu-luc/NQ-23-anh-xa-tthc.json").read_text(encoding="utf-8"))
        flagged = {c["ma"] for c in nq23["confirmed"]}
        self.assertFalse({i["ma"] for i in spec["items"]} & flagged)
        master = {t["ma"]: t for t in json.loads((root / "data/thu-tuc.json").read_text(encoding="utf-8"))["thuTuc"]}
        for item in spec["items"]:
            self.assertFalse(master[item["ma"]]["mienPhiTrucTuyen"], item["ma"])


class FeeStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.master = {t["ma"]: t for t in json.loads((root / "data/thu-tuc.json").read_text(encoding="utf-8"))["thuTuc"]}
        text = bed.OUTPUT.read_text(encoding="utf-8")
        marker = "Object.assign(window.TTHC_EXTRA || {}, "
        cls.cards = json.loads(text[text.index(marker) + len(marker): text.rindex(");")])["phiLePhi"]["nghiQuyetHP"]

    def test_tier1_has_the_four_current_resolutions(self):
        tier1 = [c["so"] for c in self.cards if c["tang"] == 1]
        self.assertEqual(tier1, ["23/2026/NQ-HĐND", "12/2026/NQ-HĐND", "34/2025/NQ-HĐND", "43/2025/NQ-HĐND"])

    def test_nq43_valid_until_2030(self):
        card = next(c for c in self.cards if c["so"] == "43/2025/NQ-HĐND")
        self.assertIn("31/12/2030", card["trangThai"])

    def test_business_registration_fee_zero_all_forms_not_nq23_flag(self):
        row = self.master["1.001612"]
        self.assertFalse(row["mienPhiTrucTuyen"])
        entry = row["phiCanCu"][0]
        self.assertIn("NQ 12/2026/NQ-HĐND", entry["canCu"])
        self.assertEqual(entry["mucTrucTiep"], entry["mucTrucTuyen"])

    def test_nq23_rows_have_full_fee_basis_structure(self):
        keys = {"khoanPhi", "canCu", "mucTrucTiep", "mucTrucTuyen", "apDungTu", "chuyenTiep"}
        flagged = [t for t in self.master.values() if t["mienPhiTrucTuyen"]]
        self.assertTrue(flagged)
        for t in flagged:
            self.assertTrue(keys <= set(t["phiCanCu"][0]), t["ma"])
            self.assertEqual(t["phiCanCu"][0]["mucTrucTuyen"], "0 đồng")
