from __future__ import annotations
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("validate_canonical_contract",ROOT/"scripts"/"validate_canonical_contract.py")
assert SPEC and SPEC.loader
MODULE=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)
class CanonicalContractTest(unittest.TestCase):
    def payload(self,name:str="Thủ tục hợp lệ")->dict:
        return {"format":"bangniemyet-vinhbao-master-data","version":3,"dataset_version":"2026.09.20","source_commit":"a"*40,"thuTuc":[{"ma":"1.000001","ten":name}]}
    def test_accepts_clean_unicode_name(self): self.assertEqual(MODULE.validate(self.payload()),[])
    def test_rejects_control_character(self): self.assertTrue(any("ký tự điều khiển" in e for e in MODULE.validate(self.payload("\x07Tên lỗi\x07"))))
    def test_rejects_cp437_marker(self): self.assertTrue(any("CP437" in e for e in MODULE.validate(self.payload("Th├╗ tß╗Ñc"))))
    def test_rejects_known_ocr_split_marker(self): self.assertTrue(any("tách chữ OCR" in e for e in MODULE.validate(self.payload("Cấp Ch ứng chỉ hành nghề đấu giá"))))
    def test_repository_dataset_passes(self):
        payload=json.loads((ROOT/"data"/"thu-tuc.json").read_text(encoding="utf-8")); self.assertEqual(MODULE.validate(payload),[])
if __name__=="__main__": unittest.main()
