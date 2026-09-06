#!/bin/bash
# Đồng bộ toàn bộ source local → GitHub (chạy trên máy đã login git/gh)
set -euo pipefail
REPO="hongdienvbhp/BangNiemYetVinhBao"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Clone $REPO"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git clone "https://github.com/${REPO}.git" "$TMP/repo"

echo "==> Copy file local (trừ .git)"
rsync -a --delete --exclude='.git' --exclude='PUSH_REMAINING.sh' "$DIR/" "$TMP/repo/"

cd "$TMP/repo"
git config user.email "hongdienvbhp@gmail.com" 2>/dev/null || true
git config user.name "hongdienvbhp" 2>/dev/null || true

git add -A
if git diff --cached --quiet; then
  echo "Không có thay đổi mới — repo đã đủ."
  exit 0
fi

git status --short | head -40
git commit -m "feat: đầy đủ mã nguồn + dữ liệu TTHC Vĩnh Bảo (473 thủ tục, thoiHan/phi đủ)"
git push origin main
echo "==> Xong: https://github.com/${REPO}"
