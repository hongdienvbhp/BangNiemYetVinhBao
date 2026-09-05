#!/bin/bash
# Chạy trên máy đã cài Git + đã đăng nhập GitHub (gh auth login hoặc git credential)
set -euo pipefail
REPO="hongdienvbhp/BangNiemYetVinhBao"
DIR="$(cd "$(dirname "$0")" && pwd)"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo ">> Clone repo..."
git clone "https://github.com/${REPO}.git" "$TMP/repo"

echo ">> Đồng bộ file local vào clone..."
rsync -a --exclude='.git' --exclude='PUSH_REMAINING.sh' "$DIR/" "$TMP/repo/"

cd "$TMP/repo"
git config user.email "hongdienvbhp@gmail.com" || true
git config user.name "hongdienvbhp" || true
git add -A
if git diff --cached --quiet; then
  echo "Không có thay đổi mới."
else
  git commit -m "feat: đầy đủ mã nguồn trang niêm yết TTHC UBND xã Vĩnh Bảo"
  git push origin main
  echo ">> Đã push: https://github.com/${REPO}"
fi
