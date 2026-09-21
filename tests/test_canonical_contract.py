import unittest

from scripts.canonical_v4 import SOURCE_COMMIT_KIND, upgrade_record_to_v4
from scripts.validate_canonical_contract import validate


def payload():
    row = upgrade_record_to_v4({
        "ma": "1.000001",
        "ten": "Thủ tục hợp lệ",
        "linhVuc": "TƯ PHÁP",
        "cap": "Xã",
        "sourceSnapshotDate": "2026-09-21",
        "sourceEvidence": [{
            "articleUrl": "https://haiphong.gov.vn/thu-tuc-hanh-chinh",
            "articleTitle": "Quyết định công bố",
            "publishedDate": "2026-09-20",
            "effectiveDate": "2026-09-20",
            "classification": "public_tthc_city_update",
            "attachmentUrl": "https://haiphong.gov.vn/attachment.pdf",
            "attachmentSha256": "a" * 64,
            "decisionNumbers": ["123/QĐ-UBND"],
            "repealContext": False,
        }],
    }, "2026-09-21")
    return {
        "format": "bangniemyet-vinhbao-master-data",
        "version": 4,
        "dataset_version": "2026.09.21",
        "source_commit": "a" * 40,
        "source_commit_kind": SOURCE_COMMIT_KIND,
        "thuTuc": [row],
    }


class CanonicalContractTests(unittest.TestCase):
    def test_accepts_verified_vinhbao_submission_link(self):
        data = payload()
        row = data["thuTuc"][0]
        row.update({
            "formalityId": "abc",
            "nopHoSoUrl": (
                "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh"
                "?formalityId=abc&provinceCode=31&wardCode=11824&commune=WARD"
            ),
            "submissionLinkStatus": "vinhbao_scope_parameters_verified",
            "nopHoSoScope": {
                "provinceCode": "31", "wardCode": "11824", "commune": "WARD"
            },
        })
        data["thuTuc"][0] = upgrade_record_to_v4(row, "2026-09-21")
        self.assertEqual(validate(data), [])

    def test_rejects_wrong_ward_submission_link(self):
        data = payload()
        row = data["thuTuc"][0]
        row.update({
            "formalityId": "abc",
            "nopHoSoUrl": (
                "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh"
                "?formalityId=abc&provinceCode=31&wardCode=99999&commune=WARD"
            ),
            "submissionLinkStatus": "vinhbao_scope_parameters_verified",
            "nopHoSoScope": {
                "provinceCode": "31", "wardCode": "99999", "commune": "WARD"
            },
        })
        data["thuTuc"][0] = upgrade_record_to_v4(row, "2026-09-21")
        self.assertTrue(any("wardCode" in error for error in validate(data)))

    def test_rejects_guidance_without_official_provenance(self):
        data = payload()
        row = data["thuTuc"][0]
        row["huongDan"] = {
            "verificationStatus": "verified_official",
            "sources": [{
                "url": "https://example.com/source",
                "sourceRole": "central_content_reference",
            }],
            "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
        }
        data["thuTuc"][0] = upgrade_record_to_v4(row, "2026-09-21")
        self.assertTrue(any("nguồn chính thức" in error or "URL không phải" in error for error in validate(data)))

    def test_accepts_verified_guidance(self):
        data = payload()
        row = data["thuTuc"][0]
        row["huongDan"] = {
            "verificationStatus": "verified_official",
            "verifiedAt": "2026-09-21",
            "sources": [{
                "url": "https://haiphong.gov.vn/thu-tuc-hanh-chinh",
                "sourceRole": "central_content_reference",
            }],
            "quyTrinh": [{"buoc": 1, "tieuDe": "Nộp hồ sơ", "noiDung": "Nộp hồ sơ theo quy định"}],
            "thanhPhanHoSo": [{"ten": "Giấy tờ A"}],
            "bieuMau": [{"ten": "Mẫu số 01", "url": "https://haiphong.gov.vn/mau-01"}],
            "lePhi": [{"ten": "Lệ phí", "mucThu": "Không thu"}],
        }
        data["thuTuc"][0] = upgrade_record_to_v4(row, "2026-09-21")
        self.assertEqual(validate(data), [])


if __name__ == "__main__":
    unittest.main()
