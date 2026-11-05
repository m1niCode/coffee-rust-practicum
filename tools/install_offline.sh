#!/usr/bin/env bash
# Установка практикума на станции без интернета из комплекта tools/make_bundle.sh.
#     bash /media/$USER/DISK/coffee_bundle/install_offline.sh ~/coffee
# Системные пакеты (python3-venv, python3-tk, libxcb-xinerama0, libxcb-cursor0) должны уже стоять.
set -euo pipefail
B="$(cd "$(dirname "$0")" && pwd)"
T="${1:-$HOME/coffee}"

mkdir -p "$T"
echo "== 1/5 Проект -> $T"
tar -xf "$B/coffee.tar" -C "$T"
cd "$T"

venv() {  # venv <папка> <папка пакетов> <пакеты...>
  local dir="$1" wh="$2"; shift 2
  [ -d "$dir" ] || python3 -m venv "$dir"
  "$dir/bin/pip" install -q --no-index --find-links "$wh" "$@"
}

echo "== 2/5 Окружение обучения"
venv .venv "$B/wheels/train" torch torchvision -r requirements.txt
echo "== 3/5 labelme / Label Studio"
venv .venv-labelme "$B/wheels/labelme" labelme
[ -d "$B/wheels/ls" ] && venv .venv-ls "$B/wheels/ls" label-studio

echo "== 4/5 Веса ImageNet"
HUB="${HF_HOME:-$HOME/.cache/huggingface}/hub"
mkdir -p "$HUB"
tar -xf "$B/hf_cache.tar" -C "$HUB"

echo "== 5/5 Мини-датасет и проверка"
.venv/bin/python tools/make_mini_dataset.py
.venv/bin/python check_env.py --offline || true
