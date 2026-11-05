#!/usr/bin/env bash
# Подготовка учебного ПК (Ubuntu 22.04/24.04) к практикуму. Запуск из папки проекта:
#     bash setup_ubuntu.sh            # всё: обучение + labelme + Label Studio
#     bash setup_ubuntu.sh --cpu      # ПК без видеокарты NVIDIA (torch без CUDA, скачивание меньше)
#     bash setup_ubuntu.sh --no-ls    # без Label Studio
# Нужен интернет (~3–4 ГБ при CUDA). Повторный запуск безопасен.
set -euo pipefail
cd "$(dirname "$0")"

CPU=0; WITH_LS=1
for arg in "$@"; do
  case "$arg" in
    --cpu) CPU=1 ;;
    --no-ls) WITH_LS=0 ;;
    *) echo "Неизвестный параметр: $arg"; exit 1 ;;
  esac
done

echo "== 1/6 Системные пакеты (нужен пароль sudo)"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip python3-tk git \
  libgl1 libglib2.0-0 libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0   # последние — для окна labelme (Qt)
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Нужен Python 3.10+"'

echo "== 2/6 Окружение обучения .venv"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
if [ "$CPU" = 1 ]; then
  .venv/bin/pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu
else
  .venv/bin/pip install -q torch torchvision          # сборка для Linux с PyPI уже включает CUDA
fi
.venv/bin/pip install -q -r requirements.txt

echo "== 3/6 labelme (отдельное окружение .venv-labelme, чтобы не конфликтовать с OpenCV/Qt)"
[ -d .venv-labelme ] || python3 -m venv .venv-labelme
.venv-labelme/bin/python -m pip install -q --upgrade pip
.venv-labelme/bin/pip install -q labelme

if [ "$WITH_LS" = 1 ]; then
  echo "== 4/6 Label Studio (отдельное окружение .venv-ls)"
  [ -d .venv-ls ] || python3 -m venv .venv-ls
  .venv-ls/bin/python -m pip install -q --upgrade pip
  .venv-ls/bin/pip install -q label-studio
else
  echo "== 4/6 Label Studio пропущен"
fi

echo "== 5/6 Учебные данные"
.venv/bin/python tools/make_label_set.py
.venv/bin/python tools/make_mini_dataset.py

echo "== 6/6 Проверка и загрузка весов ImageNet в кэш"
.venv/bin/python check_env.py || true

cat <<'EOF'

Готово. Команды на занятии (из папки проекта):
  source .venv/bin/activate && python app.py                       # приложение обучения
  .venv-labelme/bin/labelme practicum/label_set/images --labels practicum/labelme_labels.txt --nodata --autosave
  .venv-ls/bin/label-studio start --port 8080                       # Label Studio (альтернатива)
Перед занятием без интернета проверьте:  .venv/bin/python check_env.py --offline
EOF
