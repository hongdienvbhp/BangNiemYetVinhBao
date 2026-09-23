from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_master_data", ROOT / "scripts" / "build_master_data.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BuildMasterDataTitleRepairTest(unittest.TestCase):
    def test_removes_bell_delimited_suffix(self) -> None:
        self.assertEqual(
            MODULE.repair_city_name("\x07Tên thủ tục\x07(1) Trong", "9.999999"),
            "Tên thủ tục",
        )

    def test_removes_leading_bell(self) -> None:
        self.assertEqual(
            MODULE.repair_city_name("\x07Tên thủ tục", "9.999999"),
            "Tên thủ tục",
        )

    def test_priority51_verified_title_corrections(self) -> None:
        expected = {
            "1.013949": "Giao đất, cho thuê đất, chuyển mục đích sử dụng đất đối với trường hợp giao đất, cho thuê đất không đấu giá quyền sử dụng đất, không đấu thầu lựa chọn nhà đầu tư thực hiện dự án có sử dụng đất; trường hợp giao đất, cho thuê đất thông qua đấu thầu lựa chọn nhà đầu tư thực hiện dự án có sử dụng đất; giao đất và giao rừng; cho thuê đất và cho thuê rừng, gia hạn sử dụng đất khi hết thời hạn sử dụng đất",
            "1.013978": "Đăng ký đất đai, tài sản gắn liền với đất, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất lần đầu đối với hộ gia đình, cá nhân, cộng đồng dân cư, người gốc Việt Nam định cư ở nước ngoài",
            "2.000815": "Chứng thực bản sao từ bản chính giấy tờ, văn bản do cơ quan, tổ chức có thẩm quyền của Việt Nam; cơ quan, tổ chức có thẩm quyền của nước ngoài; cơ quan, tổ chức có thẩm quyền của Việt Nam liên kết với cơ quan, tổ chức có thẩm quyền của nước ngoài cấp hoặc chứng nhận",
            "2.000884": "Thủ tục chứng thực chữ ký trong các giấy tờ, văn bản (áp dụng cho cả trường hợp chứng thực điểm chỉ và trường hợp người yêu cầu chứng thực không ký, không điểm chỉ được)",
            "2.001035": "Chứng thực giao dịch liên quan đến tài sản là động sản, quyền sử dụng đất, nhà ở",
        }
        for code, title in expected.items():
            with self.subTest(code=code):
                self.assertEqual(MODULE.repair_city_name("nội dung trích xuất lỗi", code), title)


if __name__ == "__main__":
    unittest.main()
