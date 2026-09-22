# Canonical TTHC v4

## Mục tiêu

`data/thu-tuc.json` là canonical duy nhất của dự án. Schema v4 bổ sung structured provenance để mọi thuộc tính quan trọng có thể truy vết deterministic về nguồn chính thức, trước khi dùng semantic search/RAG/Agent.

Không tạo Master thứ hai. Các file `data/source-audit/*`, `data/tthc-guidance-enrichment.json` và projection chỉ là bằng chứng/đầu vào/đầu ra dẫn xuất.

## Ownership trường

### Root record

Root giữ các trường định danh, pháp lý và ánh xạ thực thi:

- `ma`, `ten`, `linhVuc`, `cap`
- `lifecycle`
- `quyetDinh`
- `formalityId`, `nopHoSoUrl`, `nopHoSoScope`, `submissionLinkStatus`
- `sourceEvidence`
- `fieldSources`

Các trường legacy root như `thoiHan`, `phi`, `phiOnline`, `dvctt`, `coQuan` được giữ tạm để tương thích consumer hiện tại; không phải owner cho dữ liệu làm giàu mới.

### huongDan

Nội dung nghiệp vụ chi tiết mới phải đi vào `huongDan`:

- `quyTrinh`
- `thanhPhanHoSo`
- `bieuMau`
- `lePhi`
- `thoiHan`
- `coQuanThucHien`
- `ketQua`
- `canCuPhapLy` (mảng citation pháp lý; không thay thế evidence về hiệu lực địa phương)
- `submissionUrl`

Mọi field được publish trong `huongDan` phải có provenance ở `fieldSources`.

## Lifecycle

```json
{
  "lifecycle": {
    "status": "active",
    "asOf": "2026-09-18",
    "effectiveFrom": "2026-09-04",
    "effectiveTo": null
  }
}
```

`status` chỉ nhận: `active`, `future_effective`, `repealed`.

Canonical public hiện hành chỉ công khai record `active`; record bãi bỏ/chưa hiệu lực tiếp tục nằm ở audit/excluded, không nhân bản vào canonical.

## Source role

Ba role duy nhất:

- `central_content_reference`: Bộ/ngành hoặc nguồn trung ương dùng để làm giàu nội dung nghiệp vụ; không được tự xác lập hiệu lực tại Vĩnh Bảo.
- `local_legal_effect`: quyết định/công bố chính thức Hải Phòng/Vĩnh Bảo xác lập hiệu lực, thẩm quyền, sửa đổi, bãi bỏ.
- `local_execution`: DVCQG/nguồn thực thi chính thức xác lập formalityId, địa bàn và URL nộp hồ sơ.

Precedence:

1. Lifecycle/phạm vi pháp lý phải có `local_legal_effect`.
2. `formalityId` và URL nộp hồ sơ phải có `local_execution`.
3. Nội dung `huongDan` có thể lấy từ `central_content_reference` hoặc `local_legal_effect`; nguồn trung ương không được thay đổi lifecycle.
4. AI/semantic matching chỉ được tạo candidate; validator deterministic mới quyết định PASS.

## Evidence và fieldSources

Mỗi evidence có `evidenceId` ổn định, `sourceRole`, URL chính thức và metadata nguồn. `fieldSources` chỉ lưu tham chiếu evidenceId, không copy nội dung nguồn:

```json
{
  "sourceEvidence": [
    {
      "evidenceId": "ev_...",
      "sourceRole": "local_legal_effect",
      "url": "https://...",
      "articleUrl": "https://...",
      "attachmentUrl": "https://...",
      "attachmentSha256": "...",
      "decisionNumbers": ["..."],
      "publishedDate": "2026-09-04",
      "effectiveDate": null,
      "repealContext": false
    }
  ],
  "fieldSources": {
    "ma": ["ev_..."],
    "lifecycle.status": ["ev_..."]
  }
}
```

## Versioning deterministic

- `dataset_version`: ngày mới nhất từ snapshot/enrichment đã kiểm chứng, nhưng không được giảm so với version canonical đã phát hành.
- `source_commit`: fingerprint SHA-1 deterministic của bundle nguồn đã kiểm chứng, tính từ Git-blob SHA của các file nguồn đầu vào.
- `priority-51-crosswalk.json` là projection/technical crosswalk có back-reference về canonical nên không tham gia fingerprint; fingerprint dùng các evidence/snapshot nguồn mà crosswalk dẫn xuất từ đó.
- `source_commit_kind = verified_source_bundle_git_sha1`.
- `source_commit` không phải SHA của commit chứa `data/thu-tuc.json`; vì vậy không có self-reference.

## Exact-search và semantic-search

Exact-search bắt buộc cho: mã TTHC, formalityId, lĩnh vực chuẩn hóa, lifecycle, quyết định, ngày hiệu lực, cơ quan/cấp thực hiện, DVCTT, phí/lệ phí cấu trúc, URL/SHA nguồn, dataset_version, source_commit.

Semantic/hybrid search áp dụng cho: tên TTHC, thành phần hồ sơ, trình tự, biểu mẫu, điều kiện/nội dung hướng dẫn, kết quả.

Luồng retrieval chuẩn: **exact filter -> structured record -> semantic retrieval trong phạm vi record/source hợp lệ -> AI tổng hợp**.
