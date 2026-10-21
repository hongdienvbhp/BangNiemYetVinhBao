#!/usr/bin/env python3
from __future__ import annotations
import json,re,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATASET=ROOT/"data/thu-tuc.json"
CONTROL=re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WORD_REPAIRS={"Ch ứng":"Chứng","tr ạm":"trạm","đi ểm":"điểm","giấy t ờ":"giấy tờ","th ẩm":"thẩm","quy ền":"quyền","nh ập":"nhập","th ấp":"thấp"}
def clean_title(value:str)->str:
    title=value
    if "\x07" in title:
        parts=[part.strip() for part in title.split("\x07") if part.strip()]
        if not parts: raise ValueError("Tên chỉ chứa ký tự điều khiển")
        title=parts[0]
    if CONTROL.search(title): raise ValueError(f"Ký tự điều khiển không được nhận diện: {title!r}")
    for old,new in WORD_REPAIRS.items(): title=title.replace(old,new)
    return unicodedata.normalize("NFC",title.strip())
def main()->int:
    payload=json.loads(DATASET.read_text(encoding="utf-8")); changed=0
    for row in payload["thuTuc"]:
        original=str(row.get("ten","")); cleaned=clean_title(original)
        if cleaned!=original: row["ten"]=cleaned; changed+=1
    DATASET.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"changed_titles":changed,"procedures":len(payload["thuTuc"])})); return 0
if __name__=="__main__": raise SystemExit(main())
