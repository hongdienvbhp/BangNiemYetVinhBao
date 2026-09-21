import unittest

from scripts.apply_guidance_enrichment import apply_enrichment
from scripts.build_tthc_tracking import classify_change


def empty_guidance(rows=None):
    return {
        "format": "bangniemyet-tthc-guidance-enrichment",
        "version": 1,
        "sourceRoles": {
            "central_content_reference": "central",
            "local_legal_effect": "local legal",
            "local_execution": "execution",
        },
        "rows": rows or [],
    }


class CanonicalTwoLayerTests(unittest.TestCase):
    def test_priority51_link_becomes_vinhbao_submission_link(self):
        master = {
            "dataset_version": "2026.09.18",
            "sourceSnapshotDate": "2026-09-18",
            "thuTuc": [{"ma": "1.000001", "formalityId": "abc"}],
            "summary": {},
        }
        priority = {"items": [{
            "code": "1.000001",
            "formalityId": "abc",
            "dvcUrl": "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh?formalityId=abc&provinceCode=31&wardCode=11824&commune=WARD",
            "liveVerifiedAt": "2026-09-20T10:00:00Z",
        }]}
        result = apply_enrichment(master, priority, empty_guidance())
        row = result["thuTuc"][0]
        self.assertEqual(row["submissionLinkStatus"], "vinhbao_scope_parameters_verified")
        self.assertIn("wardCode=11824", row["nopHoSoUrl"])
        self.assertEqual(result["dataset_version"], "2026.09.20")
        self.assertEqual(result["updatedAt"], "2026-09-20")

    def test_official_guidance_is_nested_not_a_second_master(self):
        master = {
            "dataset_version": "2026.09.18",
            "sourceSnapshotDate": "2026-09-18",
            "thuTuc": [{"ma": "1.000001"}],
            "summary": {},
        }
        priority = {"items": []}
        guidance = empty_guidance([{
            "ma": "1.000001",
            "verificationStatus": "verified_official",
            "verifiedAt": "2026-09-21",
            "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
            "sources": [{
                "id": "central-a",
                "sourceRole": "central_content_reference",
                "url": "https://moj.gov.vn/a",
            }],
            "fieldProvenance": {
                "thanhPhanHoSo": ["central-a"],
            },
        }])
        result = apply_enrichment(master, priority, guidance)
        row = result["thuTuc"][0]
        guide = row["huongDan"]
        self.assertEqual(guide["thanhPhanHoSo"][0]["ten"], "Giấy tờ A")
        self.assertEqual(guide["fieldProvenance"]["thanhPhanHoSo"], ["central-a"])
        evidence_id = next(
            item["evidenceId"]
            for item in row["sourceEvidence"]
            if item.get("url") == "https://moj.gov.vn/a"
        )
        self.assertEqual(
            row["fieldSources"]["huongDan.thanhPhanHoSo"],
            [evidence_id],
        )
        self.assertEqual(result["dataset_version"], "2026.09.21")
        self.assertEqual(result["updatedAt"], "2026-09-21")

    def test_dataset_version_never_moves_backward(self):
        master = {
            "dataset_version": "2026.09.22",
            "sourceSnapshotDate": "2026-09-18",
            "thuTuc": [{"ma": "1.000001"}],
            "summary": {},
        }
        guidance = empty_guidance([{
            "ma": "1.000001",
            "verificationStatus": "verified_official",
            "verifiedAt": "2026-09-21",
            "thoiHan": "02 ngày",
            "sources": [{
                "id": "local-a",
                "sourceRole": "local_legal_effect",
                "url": "https://haiphong.gov.vn/a",
            }],
            "fieldProvenance": {"thoiHan": ["local-a"]},
        }])
        result = apply_enrichment(master, {"items": []}, guidance)
        self.assertEqual(result["dataset_version"], "2026.09.22")
        self.assertEqual(result["updatedAt"], "2026-09-22")

    def test_cut_reduction_is_evidence_driven(self):
        kind, detail = classify_change({
            "sectionStatus": "modified",
            "context": "Thời hạn theo quy định; Sau cắt giảm: 02 ngày",
        })
        self.assertEqual(kind, "reduced")
        self.assertIn("cắt giảm", detail)


if __name__ == "__main__":
    unittest.main()
