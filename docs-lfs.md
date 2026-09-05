# Git LFS — cấu hình tối ưu dự án Vĩnh Bảo

## Khi nào dùng LFS?

| Loại file | Khuyến nghị | Lý do |
|-----------|-------------|--------|
| `.png` `.xlsx` `.pdf` `.zip` | **LFS** | Nhị phân, không diff |
| `.js` `.json` `.css` `.html` `.csv` `.svg` `.md` | **Git thường** | Text, cần xem diff PR |
| File > ~5–10 MB thay đổi thường xuyên | Cân nhắc LFS | Tránh phình history |

Repo hiện **~150 KB** — LFS chủ yếu chuẩn bị cho logo PNG, Excel nguồn, PDF sau này.

## Cài đặt (máy dev)

```bash
# Windows: winget install GitHub.GitLFS
# macOS:   brew install git-lfs
# Ubuntu:  sudo apt install git-lfs

git lfs install
cd BangNiemYetVinhBao
git lfs track   # xem pattern trong .gitattributes
git add .gitattributes
git add assets/logo-hcc.png data/*.xlsx
git commit -m "chore: track binary với Git LFS"
git push
```

## Clone nhanh (CI / máy không cần ảnh Excel)

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/hongdienvbhp/BangNiemYetVinhBao.git
# Chỉ tải pointer; khi cần file thật:
# git lfs pull
```

## Không nên

- Đưa `js/data.js` / `data/thu-tuc.json` vào LFS → mất diff, review khó, quota LFS GitHub (1 GB free) lãng phí.
- Track từng file cụ thể nếu đã có pattern `*.png`.
