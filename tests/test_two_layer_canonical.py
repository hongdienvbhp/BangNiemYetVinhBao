import unittest

from scripts.apply_guidance_enrichment import apply_enrichment
from scripts.build_tthc_tracking import classify_change


class CanonicalTwoLayerTests(unittest.TestCase):
    def test_priority51_link_becomes_vinhbao_submission_link(self):
        master = {"thuTuc": [{"ma": "1.000001", "formalityId": "abc"}], "summary": {}}
        priority = {"items": [{
            "code": "1.000001",
            "formalityId": "abc",
            "dvcUrl": "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh?formalityId=abc&provinceCode=31&wardCode=11824&commune=WARD",
        }]}
        guidance = {
            "format": "bangniemyet-tthc-guidance-enrichment",
            "version": 1,
            "rows": [],
        }
        result = apply_enrichment(master, priority, guidance)
        row = result["thuTuc"][0]
        self.assertEqual(row["submissionLinkStatus"], "vinhbao_scope_parameters_verified")
        self.assertIn("wardCode=11824", row["nopHoSoUrl"])

    def test_official_guidance_is_nested_not_a_second_master(self):
        master = {"thuTuc": [{"ma": "1.000001"}], "summary": {}}
        priority = {"items": []}
        guidance = {
            "format": "bangniemyet-tthc-guidance-enrichment",
            "version": 1,
            "rows": [{
                "ma": "1.000001",
                "verificationStatus": "verified_official",
                "verifiedAt": "2026-09-21",
                "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
                "sources": [{"url": "https://haiphong.gov.vn/a"}],
            }],
        }
        result = apply_enrichment(master, priority, guidance)
        self.assertEqual(result["thuTuc"][0]["huongDan"]["thanhPhanHoSo"][0]["ten"], "Giấy tờ A")

    def test_cut_reduction_is_evidence_driven(self):
        kind, detail = classify_change({
            "sectionStatus": "modified",
            "context": "Thời hạn theo quy định; Sau cắt giảm: 02 ngày",
        })
        self.assertEqual(kind, "reduced")
        self.assertIn("cắt giảm", detail)


if __name__ == "__main__":
    unittest.main()
