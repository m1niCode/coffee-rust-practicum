#!/usr/bin/env bash
# Скачать обученные модели exp1–exp3 из GitHub Release в OUT/<эксперимент>/.
#     bash tools/download_models.sh
# Репозиторий определяется по git remote origin; другой — REPO=owner/name bash tools/download_models.sh
set -euo pipefail
cd "$(dirname "$0")/.."

TAG="${TAG:-models-v1}"
if [ -z "${REPO:-}" ]; then
  url="$(git remote get-url origin)"
  REPO="$(echo "$url" | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
fi
BASE="https://github.com/$REPO/releases/download/$TAG"

for pair in "exp1 best_model.pth" "exp2 best_model_2.pth" "exp3 best_model_3.pth"; do
  set -- $pair
  dst="OUT/$1/$2"
  if [ -s "$dst" ]; then
    echo "[есть] $dst"
    continue
  fi
  echo "[скачиваю] $dst"
  mkdir -p "OUT/$1"
  curl -fL --retry 3 -o "$dst.part" "$BASE/$1_$2" && mv "$dst.part" "$dst"
done
echo "Готово."
