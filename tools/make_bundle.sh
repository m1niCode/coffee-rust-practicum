#!/usr/bin/env bash
# Собрать комплект для переноса на жёстком диске (станции без интернета).
# Запускать на Ubuntu той же версии, что станции, в проекте, где setup_ubuntu.sh уже отработал:
#     bash tools/make_bundle.sh /media/$USER/DISK/coffee_bundle
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="${1:?Укажите папку назначения, например /media/$USER/DISK/coffee_bundle}"
mkdir -p "$DEST/wheels"

[ -x .venv/bin/python ] || { echo "Нет .venv — сначала bash setup_ubuntu.sh"; exit 1; }
ls OUT/exp*/best_model*.pth >/dev/null 2>&1 || echo "!! Моделей .pth нет — bash tools/download_models.sh"

echo "== 1/4 Проект -> coffee.tar"
tar --exclude='./.venv' --exclude='./.venv-*' --exclude='./practicum/data_mini*' --exclude='./practicum/my_*' \
    --exclude='__pycache__' --exclude='./web/node_modules' --exclude='./reference' --exclude='./OUT_test' \
    -cf "$DEST/coffee.tar" .

echo "== 2/4 Пакеты для обучения (torch той же сборки, что установлен: CUDA или CPU)"
CUDA="$(.venv/bin/python -c 'import torch; print(torch.version.cuda or "")')"
if [ -n "$CUDA" ]; then
  .venv/bin/pip download -q -d "$DEST/wheels/train" torch torchvision -r requirements.txt
else
  .venv/bin/pip download -q -d "$DEST/wheels/train" torch torchvision --index-url https://download.pytorch.org/whl/cpu
  .venv/bin/pip download -q -d "$DEST/wheels/train" -r requirements.txt
fi

echo "== 3/4 labelme и Label Studio"
.venv-labelme/bin/pip download -q -d "$DEST/wheels/labelme" labelme
if [ -x .venv-ls/bin/pip ]; then
  .venv-ls/bin/pip download -q -d "$DEST/wheels/ls" label-studio
fi

echo "== 4/4 Веса ImageNet и установщик"
HUB="${HF_HOME:-$HOME/.cache/huggingface}/hub"
ls -d "$HUB"/models--smp-hub--resnet*.imagenet >/dev/null || { echo "Нет весов в $HUB — запустите check_env.py с интернетом"; exit 1; }
tar -C "$HUB" -cf "$DEST/hf_cache.tar" $(cd "$HUB" && ls -d models--smp-hub--resnet*.imagenet)
cp tools/install_offline.sh "$DEST/"

du -sh "$DEST"
echo "Готово. На станции: bash $DEST/install_offline.sh ~/coffee"
