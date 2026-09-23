import unittest

from scripts.fetch_priority50_process_forms import extract_dvc_detail, extract_moit_2001283


class Priority50ProcessFormsTests(unittest.TestCase):
    def test_extracts_process_and_named_form(self):
        payload = {
            "code": "OK",
            "data": {
                "id": "fid-1",
                "code": "1.000001",
                "executionSteps": [
                    {"name": "", "description": "Bước xử lý chính thức."},
                ],
                "executionCases": [{
                    "profileComponents": [{
                        "name": "Tờ khai đề nghị theo mẫu",
                        "hasElectronicForm": False,
                        "attachments": [],
                    }]
                }],
            },
        }
        process, forms = extract_dvc_detail(payload, "1.000001", "fid-1")
        self.assertEqual(process[0]["buoc"], 1)
        self.assertEqual(process[0]["noiDung"], "Bước xử lý chính thức.")
        self.assertEqual(forms[0]["ten"], "Tờ khai đề nghị theo mẫu")
        self.assertEqual(forms[0]["trangThai"], "published_without_download_url")

    def test_no_form_is_explicit_not_published(self):
        payload = {
            "code": "OK",
            "data": {
                "id": "fid-1",
                "code": "1.000001",
                "executionSteps": [{"name": "Bước 1", "description": "Xử lý."}],
                "executionCases": [{"profileComponents": [{
                    "name": "Bản sao giấy tờ tùy thân",
                    "hasElectronicForm": False,
                    "attachments": [],
                }]}],
            },
        }
        _, forms = extract_dvc_detail(payload, "1.000001", "fid-1")
        self.assertEqual(forms, [{
            "ten": "Nguồn DVCQG chính thức không công bố biểu mẫu/tờ khai riêng cho thủ tục này.",
            "trangThai": "not_published",
        }])

    def test_rejects_wrong_tthc_code(self):
        payload = {
            "code": "OK",
            "data": {
                "id": "fid-1",
                "code": "9.999999",
                "executionSteps": [{"description": "Xử lý."}],
                "executionCases": [],
            },
        }
        with self.assertRaisesRegex(ValueError, "TTHC code mismatch"):
            extract_dvc_detail(payload, "1.000001", "fid-1")

    def test_extracts_moit_process_and_form_link(self):
        body = """
        <html><body>
        <div>Mã thủ tục</div><div>2.001283</div>
        <div>Trình tự thực hiện</div><p>Nộp hồ sơ.</p><p>Cơ quan xử lý hồ sơ.</p>
        <div>Cách thức thực hiện</div>
        <table><tr><th>Mẫu đơn, tờ khai</th></tr>
        <tr><td><a href="https://csdl.dichvucong.gov.vn/file/mau05.docx">Mẫu số 05.docx</a></td></tr></table>
        </body></html>
        """.encode()
        process, forms = extract_moit_2001283(body)
        self.assertIn("Nộp hồ sơ", process[0]["noiDung"])
        self.assertEqual(forms[0]["ten"], "Mẫu số 05.docx")
        self.assertTrue(forms[0]["url"].startswith("https://csdl.dichvucong.gov.vn/"))


if __name__ == "__main__":
    unittest.main()
