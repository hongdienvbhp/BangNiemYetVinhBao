import hashlib
import json
import unittest
from pathlib import Path

from scripts.build_online_fee_policy_candidates import (
    CANONICAL,
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
        cls.result = build(cls.canonical, load(ENRICHMENT), cls.policy)

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
        path = ROOT / self.policy["evidence"]["filePath"]
        data = path.read_bytes()
        if data.startswith(b"version https://git-lfs"):
            self.assertIn(self.policy["evidence"]["attachmentSha256"].encode(), data)
        else:
            self.assertEqual(hashlib.sha256(data).hexdigest(), self.policy["evidence"]["attachmentSha256"])

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
        self.assertEqual(rows[0]["confidence"], "medium")


if __name__ == "__main__":
    unittest.main()
