import unittest

from scripts.validate_tthc_guidance import validate, validate_vinhbao_submission_url


def base_payload(rows=None):
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


class GuidanceEnrichmentTests(unittest.TestCase):
    def test_empty_contract_is_valid(self):
        self.assertEqual(validate(base_payload()), [])

    def test_vinhbao_submission_url_requires_exact_locality(self):
        url = (
            "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh"
            "?formalityId=abc&provinceCode=31&wardCode=11824&commune=WARD"
        )
        self.assertEqual(validate_vinhbao_submission_url(url, "abc"), [])
        bad = url.replace("wardCode=11824", "wardCode=99999")
        self.assertTrue(validate_vinhbao_submission_url(bad, "abc"))

    def test_guidance_requires_official_source(self):
        payload = base_payload([{
            "ma": "1.000001",
            "verificationStatus": "verified_official",
            "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
            "sources": [{
                "id": "central-a",
                "sourceRole": "central_content_reference",
                "url": "https://example.com/a",
            }],
            "fieldProvenance": {"thanhPhanHoSo": ["central-a"]},
        }])
        self.assertTrue(any("URL chính thức" in error for error in validate(payload)))

    def test_each_substantive_field_requires_existing_source_id(self):
        payload = base_payload([{
            "ma": "1.000001",
            "verificationStatus": "verified_official",
            "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
            "sources": [{
                "id": "central-a",
                "sourceRole": "central_content_reference",
                "url": "https://moj.gov.vn/a",
            }],
            "fieldProvenance": {"thanhPhanHoSo": ["missing-source"]},
        }])
        self.assertTrue(any("không tồn tại" in error for error in validate(payload)))

    def test_submission_url_requires_local_execution_provenance(self):
        url = (
            "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh"
            "?formalityId=abc&provinceCode=31&wardCode=11824&commune=WARD"
        )
        payload = base_payload([{
            "ma": "1.000001",
            "formalityId": "abc",
            "verificationStatus": "verified_official",
            "submissionUrl": url,
            "sources": [{
                "id": "central-a",
                "sourceRole": "central_content_reference",
                "url": "https://moj.gov.vn/a",
            }],
            "fieldProvenance": {"submissionUrl": ["central-a"]},
        }])
        self.assertTrue(any("local_execution" in error for error in validate(payload)))

    def test_verified_multi_source_provenance_passes(self):
        url = (
            "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh"
            "?formalityId=abc&provinceCode=31&wardCode=11824&commune=WARD"
        )
        payload = base_payload([{
            "ma": "1.000001",
            "formalityId": "abc",
            "verificationStatus": "verified_official",
            "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
            "thoiHan": "02 ngày làm việc",
            "submissionUrl": url,
            "sources": [
                {
                    "id": "central-a",
                    "sourceRole": "central_content_reference",
                    "url": "https://moj.gov.vn/a",
                },
                {
                    "id": "local-a",
                    "sourceRole": "local_legal_effect",
                    "url": "https://haiphong.gov.vn/a",
                },
                {
                    "id": "execution-a",
                    "sourceRole": "local_execution",
                    "url": url,
                },
            ],
            "fieldProvenance": {
                "thanhPhanHoSo": ["central-a"],
                "thoiHan": ["local-a"],
                "submissionUrl": ["execution-a"],
            },
        }])
        self.assertEqual(validate(payload), [])

    def test_legal_basis_requires_field_provenance(self):
        payload = base_payload([{
            "ma": "1.000001",
            "verificationStatus": "verified_official",
            "canCuPhapLy": ["Nghị định 151/2026/NĐ-CP"],
            "sources": [{
                "id": "central-a",
                "sourceRole": "central_content_reference",
                "url": "https://moj.gov.vn/a",
            }],
            "fieldProvenance": {},
        }])
        self.assertTrue(any("fieldProvenance.canCuPhapLy" in error for error in validate(payload)))

    def test_legal_basis_with_official_content_provenance_passes(self):
        payload = base_payload([{
            "ma": "1.000001",
            "verificationStatus": "verified_official",
            "canCuPhapLy": ["Nghị định 151/2026/NĐ-CP"],
            "sources": [{
                "id": "central-a",
                "sourceRole": "central_content_reference",
                "url": "https://moj.gov.vn/a",
            }],
            "fieldProvenance": {"canCuPhapLy": ["central-a"]},
        }])
        self.assertEqual(validate(payload), [])

    def test_dvctt_requires_local_execution_provenance(self):
        payload = {
            "format": "bangniemyet-tthc-guidance-enrichment",
            "version": 1,
            "rows": [{
                "ma": "1.000001",
                "verificationStatus": "verified_official",
                "dvctt": {"accessUrl": "https://dichvucong.gov.vn/a"},
                "sources": [{
                    "id": "content",
                    "url": "https://haiphong.gov.vn/a",
                    "sourceRole": "central_content_reference",
                }],
                "fieldProvenance": {"dvctt": ["content"]},
            }],
        }
        self.assertTrue(any("dvctt" in error and "local_execution" in error for error in validate(payload)))


if __name__ == "__main__":
    unittest.main()
