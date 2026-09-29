import hashlib
import json
import unittest
from pathlib import Path

from scripts.build_online_fee_policy_candidates import (
    CANONICAL,
    DIRECT_POLICY,
    ENRICHMENT,
    OUTPUT,
    POLICY,
    build,
    classify,
)
from scripts.canonical_v4 import evidence_id

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


class OnlineFeePolicyCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load(POLICY)
        cls.canonical = load(CANONICAL)
        cls.direct = load(DIRECT_POLICY)
        cls.result = build(cls.canonical, load(ENRICHMENT), cls.policy, cls.direct)
        cls.by_code = {r["ma"]: r for r in cls.result["rows"]}

    def test_output_file_is_deterministic_build(self):
        expected = json.dumps(self.result, ensure_ascii=False, indent=2) + "\n"
        self.assertEqual(OUTPUT.read_text(encoding="utf-8"), expected)

    def test_policy_lists_exactly_eleven_items_with_zero_rate(self):
        items = self.policy["feeItems"]
        self.assertEqual(len(items), 11)
        self.assertEqual(sum(i["kind"] == "lệ phí" for i in items), 4)
        self.assertEqual(sum(i["kind"] == "phí" for i in items), 7)
        self.assertTrue(all(i["onlineRate"] == "0 đồng" for i in items))
        self.assertEqual(self.policy["document"]["effectiveDate"], "2026-08-08")

    def test_evidence_hash_matches_stored_pdf(self):
        for doc in (self.policy, self.direct):
            path = ROOT / doc["evidence"]["filePath"]
            data = path.read_bytes()
            if data.startswith(b"version https://git-lfs"):
                self.assertIn(doc["evidence"]["attachmentSha256"].encode(), data)
            else:
                self.assertEqual(hashlib.sha256(data).hexdigest(), doc["evidence"]["attachmentSha256"])

    def test_direct_rates_come_from_nq34_tables(self):
        row = self.by_code["1.012783"]  # Cấp đổi GCN
        rates = {r["table"] + ":" + r["row"]: r["rates"] for r in row["directRates"]}
        self.assertEqual(rates["PL1:canhan.capDoiCapLai"], {"dat": 25000, "taiSan": 25000, "datVaTaiSan": 30000})
        self.assertEqual(rates["PL2:canhan.capDoiCapLai"], {"dat": 100000, "taiSan": 100000, "datVaTaiSan": 115000})
        secured = self.by_code["1.011441"]
        self.assertEqual(secured["directRates"][0]["row"], "canhan.dangKy.trucTiep")
        self.assertEqual(secured["confidence"], "high")

    def test_land_change_and_donation_rules(self):
        self.assertEqual(self.by_code["1.013831"]["confidence"], "high")
        self.assertEqual(self.by_code["1.013979"]["applicability"], "already_exempt")
        self.assertEqual(self.direct["conflictWithNq23"]["status"], "needs_authority_confirmation")

    def test_civil_status_direct_rate_is_marked_missing(self):
        row = self.by_code["1.001193"]
        self.assertEqual(row["directRates"], [])
        self.assertIn("cần bổ sung", row["directRateNote"])

    def test_rows_are_candidate_only_and_reference_evidence(self):
        ev = evidence_id(self.policy["evidence"])
        codes = {r["ma"] for r in self.canonical["thuTuc"]}
        for row in self.result["rows"]:
            self.assertEqual(row["promotionStatus"], "candidate_only")
            self.assertEqual(row["evidenceId"], ev)
            self.assertIn(row["ma"], codes)
            if row["applicability"] == "out_of_scope":
                self.assertIsNone(row["proposedOnlineFee"])
            else:
                self.assertEqual(row["proposedOnlineFee"], "0 đồng")

    def test_copy_extract_fee_is_not_civil_status_fee(self):
        rows = classify({"ten": "Cấp bản sao Trích lục hộ tịch, bản sao Giấy khai sinh", "linhVuc": "HỘ TỊCH"})
        self.assertEqual(rows[0]["applicability"], "out_of_scope")

    def test_already_issued_certificate_wording_is_not_new_issuance(self):
        rows = classify({"ten": "Thu hồi Giấy chứng nhận đã cấp không đúng quy định", "linhVuc": "ĐẤT ĐAI"})
        self.assertEqual(rows[0]["confidence"], "low")
        rows = classify({"ten": "Cấp đổi Giấy chứng nhận quyền sử dụng đất", "linhVuc": "ĐẤT ĐAI"})
        self.assertEqual((rows[0]["confidence"], rows[0]["applicability"]), ("high", "applies"))
        rows = classify({"ten": "Đăng ký tài sản gắn liền với thửa đất đã được cấp Giấy chứng nhận", "linhVuc": "ĐẤT ĐAI"})
        self.assertEqual((rows[0]["confidence"], rows[0]["applicability"]), ("high", "applies"))


if __name__ == "__main__":
    unittest.main()
