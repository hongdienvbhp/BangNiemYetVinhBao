import unittest

from scripts.validate_canonical_contract import validate


def payload():
    return {
        "format": "bangniemyet-vinhbao-master-data",
        "version": 3,
        "dataset_version": "2026.09.21",
        "source_commit": "a" * 40,
        "thuTuc": [{"ma": "1.000001", "ten": "Thủ tục hợp lệ", "formalityId": "abc"}],
    }


class CanonicalContractTests(unittest.TestCase):
    def test_accepts_verified_vinhbao_submission_link(self):
        data = payload()
        data["thuTuc"][0].update({
            "nopHoSoUrl": (
                "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh"
                "?formalityId=abc&provinceCode=31&wardCode=11824&commune=WARD"
            ),
            "submissionLinkStatus": "vinhbao_scope_parameters_verified",
        })
        self.assertEqual(validate(data), [])

    def test_rejects_wrong_ward_submission_link(self):
        data = payload()
        data["thuTuc"][0].update({
            "nopHoSoUrl": (
                "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh"
                "?formalityId=abc&provinceCode=31&wardCode=99999&commune=WARD"
            ),
            "submissionLinkStatus": "vinhbao_scope_parameters_verified",
        })
        self.assertTrue(any("wardCode" in error for error in validate(data)))

    def test_rejects_guidance_without_official_provenance(self):
        data = payload()
        data["thuTuc"][0]["huongDan"] = {
            "verificationStatus": "verified_official",
            "sources": [{"url": "https://example.com/source"}],
            "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
        }
        self.assertTrue(any("nguồn chính thức" in error for error in validate(data)))

    def test_accepts_verified_guidance(self):
        data = payload()
        data["thuTuc"][0]["huongDan"] = {
            "verificationStatus": "verified_official",
            "verifiedAt": "2026-09-21",
            "sources": [{"url": "https://haiphong.gov.vn/thu-tuc-hanh-chinh"}],
            "quyTrinh": [{"buoc": 1, "tieuDe": "Nộp hồ sơ", "noiDung": "Nộp hồ sơ theo quy định"}],
            "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
            "bieuMau": [{"ten": "Mẫu số 01", "url": "https://haiphong.gov.vn/mau-01"}],
            "lePhi": [{"ten": "Lệ phí", "mucThu": "Không thu"}],
        }
        self.assertEqual(validate(data), [])


if __name__ == "__main__":
    unittest.main()
