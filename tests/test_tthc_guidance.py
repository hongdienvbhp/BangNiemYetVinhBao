import unittest

from scripts.validate_tthc_guidance import validate, validate_vinhbao_submission_url


class GuidanceEnrichmentTests(unittest.TestCase):
    def test_empty_contract_is_valid(self):
        payload = {
            "format": "bangniemyet-tthc-guidance-enrichment",
            "version": 1,
            "rows": [],
        }
        self.assertEqual(validate(payload), [])

    def test_vinhbao_submission_url_requires_exact_locality(self):
        url = (
            "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh"
            "?formalityId=abc&provinceCode=31&wardCode=11824&commune=WARD"
        )
        self.assertEqual(validate_vinhbao_submission_url(url, "abc"), [])
        bad = url.replace("wardCode=11824", "wardCode=99999")
        self.assertTrue(validate_vinhbao_submission_url(bad, "abc"))

    def test_guidance_requires_official_source(self):
        payload = {
            "format": "bangniemyet-tthc-guidance-enrichment",
            "version": 1,
            "rows": [{
                "ma": "1.000001",
                "verificationStatus": "verified_official",
                "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
                "sources": [{"url": "https://example.com/a", "sourceRole": "central_content_reference"}],
            }],
        }
        self.assertTrue(validate(payload))

    def test_guidance_requires_source_role(self):
        payload = {
            "format": "bangniemyet-tthc-guidance-enrichment",
            "version": 1,
            "rows": [{
                "ma": "1.000001",
                "verificationStatus": "verified_official",
                "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
                "sources": [{"url": "https://haiphong.gov.vn/a"}],
            }],
        }
        self.assertTrue(any("sourceRole" in error for error in validate(payload)))


if __name__ == "__main__":
    unittest.main()
