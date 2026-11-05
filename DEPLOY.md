# Развёртывание на рабочих станциях (Ubuntu)

Два способа: **A** — из GitHub (нужен интернет на станции), **B** — с жёсткого диска (без интернета).
После любого из них сценарий занятия — в [PRACTICUM.md](PRACTICUM.md).

## Что входит в проект

| Часть | Размер | Где |
|---|---|---|
| Код, интерфейс (`web/dist`), инструменты, документация | ~3 МБ | репозиторий |
| Датасет `train/ valid/ test/` (CC BY 4.0, см. `DATASET_LICENSE.txt`) | ~63 МБ | репозиторий |
| Набор для разметки `practicum/label_set/` | ~1 МБ | репозиторий |
| Результаты экспериментов `OUT/exp1–3` (графики, метрики) | ~3 МБ | репозиторий |
| Модели `OUT/exp*/best_model*.pth` | 235 МБ | GitHub Release `models-v1` |
| Python-пакеты (torch с CUDA и др.) | ~3–4 ГБ | ставятся `setup_ubuntu.sh` |
| Веса ImageNet для энкодеров | ~200 МБ | `~/.cache/huggingface` после `check_env.py` |

## A. Из GitHub (на каждой станции, ~15–30 мин)

```bash
git clone https://github.com/m1niCode/coffee-rust-practicum.git ~/coffee && cd ~/coffee
bash tools/download_models.sh          # модели exp1–exp3 из Release
bash setup_ubuntu.sh                   # пакеты, окружения, мини-датасет, проверка (--cpu без NVIDIA)
.venv/bin/python check_env.py --offline
```

## B. Жёсткий диск (без интернета на станциях)

**Собрать один раз** на Ubuntu-машине **той же версии**, что станции (та же версия Python), с интернетом:

```bash
cd ~/coffee                            # проект после способа A, всё уже установлено и проверено
bash tools/make_bundle.sh /media/$USER/DISK/coffee_bundle
```

Что окажется на диске (`coffee_bundle/`, ~4–5 ГБ):

| Папка / файл | Содержимое |
|---|---|
| `coffee.tar` | проект целиком: код, данные, модели `.pth`, `label_set` (без `.venv`) |
| `wheels/train`, `wheels/labelme`, `wheels/ls` | все pip-пакеты для трёх окружений (`pip download`) |
| `hf_cache.tar` | веса ImageNet для resnet18/34/50 |
| `install_offline.sh` | установка на станции из этих файлов |

**На каждой станции** (системные пакеты `python3-venv python3-tk libxcb-*` должны быть в образе
или ставятся с локального зеркала apt):

```bash
bash /media/$USER/DISK/coffee_bundle/install_offline.sh ~/coffee
cd ~/coffee && .venv/bin/python check_env.py --offline
```

Скрипт распаковывает проект, создаёт `.venv`, `.venv-labelme`, `.venv-ls` из локальных пакетов
(`pip install --no-index --find-links`), кладёт веса в `~/.cache/huggingface` и собирает мини-датасет.

## Перед занятием (на каждой станции)

1. `check_env.py --offline` → «Всё готово к занятию».
2. `source .venv/bin/activate && python app.py` → открылся браузер, в «Результатах» видны exp1–exp3.
3. `.venv-labelme/bin/labelme practicum/label_set/images` → окно открывается.
