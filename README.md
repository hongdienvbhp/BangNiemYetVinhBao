# Bảng Niêm Yết Thủ Tục Hành Chính — UBND xã Vĩnh Bảo

Trang web công khai niêm yết thủ tục hành chính thuộc thẩm quyền giải quyết của **UBND xã Vĩnh Bảo** (thành phố Hải Phòng).

~473 TTHC cấp xã · link Cổng DVCQG (formalityId + đơn vị Vĩnh Bảo).

---

## Repo

https://github.com/hongdienvbhp/BangNiemYetVinhBao

## Chạy local

```bash
git clone https://github.com/hongdienvbhp/BangNiemYetVinhBao.git
cd BangNiemYetVinhBao
python -m http.server 8080
# → http://localhost:8080
```

## Cấu trúc

```
index.html, css/styles.css, js/{config,data,extra-data,app}.js
data/thu-tuc.json, data/formalityId-mapping-mau.csv, data/phu-luc/
manifest.json, sw.js, netlify.toml, vercel.json
```

## Deploy

- **Netlify**: kéo thả thư mục / publish = `.`
- **Vercel**: `npx vercel --prod`
- **GitHub Pages**: Settings → Pages → branch `main` / root

## formalityId (DVCQG)

Điền UUID vào `data/formalityId-mapping-mau.csv` rồi cập nhật `data/thu-tuc.json`.

Mẫu đã có: `2.000942` → `019d2bfd-95d6-778f-889b-e3045003fa5e`

UUID tỉnh HP: `019bad30-cd83-76ea-9f9a-bc6cebad4138`  
UUID xã Vĩnh Bảo: `019bad30-cd84-7750-aaa5-8100fc7ceef8`  
provinceCode=31 · wardCode=11824

## Liên hệ

**TT PVHCC xã Vĩnh Bảo** — Đường 20/8, xã Vĩnh Bảo, TP Hải Phòng  
Hotline: 0823.919.686 · 0967.311.138
