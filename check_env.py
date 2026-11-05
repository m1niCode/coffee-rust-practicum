# -*- coding: utf-8 -*-
"""Проверка ПК перед практикумом: python check_env.py

Проверяет Python и библиотеки, видеокарту, кэш предобученных весов (при первом запуске скачивает их —
нужен интернет), данные, интерфейс и программы разметки. В конце — замер скорости обучения.

    python check_env.py            # полная проверка
    python check_env.py --offline  # убедиться, что всё работает без интернета
    python check_env.py --no-bench # без замера скорости
"""
import argparse
import importlib
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
OK, WARN, FAIL = "  [OK]  ", "  [!!]  ", "  [XX]  "
problems = []


def say(status, text, fix=""):
    print(status + text)
    if status == FAIL:
        problems.append(text + (" -> " + fix if fix else ""))
    elif fix:
        print("          " + fix)


def section(title):
    print("\n" + title)


def check_python():
    section("Python")
    v = sys.version_info
    if v >= (3, 10):
        say(OK, "Python %d.%d.%d (%s)" % (v.major, v.minor, v.micro, sys.executable))
    else:
        say(FAIL, "Python %d.%d — нужен 3.10 или новее" % (v.major, v.minor), "sudo apt install python3.12-venv")
    if sys.prefix == sys.base_prefix:
        say(WARN, "Виртуальное окружение не активно", "source .venv/bin/activate")


def check_libs():
    section("Библиотеки")
    libs = [("torch", "torch"), ("torchvision", "torchvision"), ("segmentation_models_pytorch", "smp"),
            ("albumentations", "albumentations"), ("cv2", "opencv"), ("numpy", "numpy"), ("pandas", "pandas"),
            ("matplotlib", "matplotlib"), ("fastapi", "fastapi"), ("uvicorn", "uvicorn"),
            ("multipart", "python-multipart")]
    ok = True
    for mod, name in libs:
        try:
            m = importlib.import_module(mod)
            say(OK, "%-18s %s" % (name, getattr(m, "__version__", "")))
        except Exception as e:
            ok = False
            say(FAIL, "%-18s не установлен (%s)" % (name, type(e).__name__), "pip install -r requirements.txt")
    try:
        import tkinter  # noqa: F401
        say(OK, "tkinter (кнопка «Обзор…»)")
    except Exception:
        say(WARN, "tkinter нет: пути к папкам придётся вписывать вручную", "sudo apt install python3-tk")
    return ok


def check_gpu():
    section("Видеокарта")
    import torch
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        say(OK, "%s, %.1f ГБ памяти, CUDA %s" % (p.name, p.total_memory / 2**30, torch.version.cuda))
        return "cuda"
    hint = ("torch собран без CUDA — переустановите: pip install torch torchvision"
            if torch.version.cuda is None else "проверьте драйвер: nvidia-smi")
    say(WARN, "Видеокарта не найдена, обучение пойдёт на процессоре (в 10–30 раз медленнее)", hint)
    return "cpu"


def check_weights(offline):
    section("Предобученные веса ImageNet (кэш)")
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
    import segmentation_models_pytorch as smp
    for enc in ("resnet18", "resnet34", "resnet50"):
        t = time.time()
        try:
            smp.Unet(encoder_name=enc, encoder_weights="imagenet", in_channels=3, classes=1)
            say(OK, "%s (%.0f с)" % (enc, time.time() - t))
        except Exception as e:
            say(FAIL if enc == "resnet18" else WARN, "%s: веса не загружены (%s)" % (enc, type(e).__name__),
                "запустите check_env.py с интернетом, веса сохранятся в кэш")


def count_pairs(folder):
    from core.data import find_pairs
    if not os.path.isdir(folder):
        return None
    pairs = find_pairs(folder, need_mask=False)
    return len(pairs), sum(1 for _, m in pairs if m)


def check_data():
    section("Данные")
    sys.path.insert(0, ROOT)
    for rel, need in (("train", 405), ("valid", 101), ("test", 100)):
        n = count_pairs(os.path.join(ROOT, rel))
        if n is None:
            say(FAIL, "%s/ нет" % rel)
        else:
            say(OK if n[1] >= need else WARN, "%-22s фото %d, с маской %d" % (rel + "/", *n))
    for rel in ("practicum/data_mini/train", "practicum/data_mini/valid", "practicum/data_mini/test"):
        n = count_pairs(os.path.join(ROOT, rel))
        if n is None:
            say(FAIL, "%s нет" % rel, "python tools/make_mini_dataset.py")
        else:
            say(OK, "%-22s фото %d, с маской %d" % (rel.replace("practicum/", ""), *n))
    ls = os.path.join(ROOT, "practicum", "label_set")
    n_img = len([f for f in os.listdir(os.path.join(ls, "images")) if f.endswith(".jpg")]) if os.path.isdir(ls) else 0
    say(OK if n_img else FAIL, "label_set: листьев для разметки %d" % n_img, "" if n_img else "python tools/make_label_set.py")
    out = os.path.join(ROOT, "OUT")
    exps = sorted(d for d in os.listdir(out) if os.path.isdir(os.path.join(out, d))) if os.path.isdir(out) else []
    say(OK if exps else WARN, "Готовые эксперименты в OUT/: %s" % (", ".join(exps) or "нет"))


def check_apps():
    section("Интерфейс и программы разметки")
    idx = os.path.join(ROOT, "web", "dist", "index.html")
    say(OK if os.path.exists(idx) else FAIL, "Интерфейс web/dist собран", "" if os.path.exists(idx) else "git checkout feature/new-ui")
    for name, venv, exe in (("labelme", ".venv-labelme", "labelme"), ("Label Studio", ".venv-ls", "label-studio")):
        local = os.path.join(ROOT, venv, "bin", exe)
        found = local if os.path.exists(local) else shutil.which(exe)
        if found:
            say(OK, "%s: %s" % (name, found))
        else:
            say(WARN, "%s не установлен" % name, "bash setup_ubuntu.sh")
    import socket
    s = socket.socket()
    busy = s.connect_ex(("127.0.0.1", 8765)) == 0
    s.close()
    say(WARN if busy else OK, "Порт 8765 " + ("занят — приложение уже запущено?" if busy else "свободен"))


def bench(device):
    section("Замер скорости обучения (U-Net resnet18, 256 px, batch 8)")
    import segmentation_models_pytorch as smp
    import torch
    model = smp.Unet(encoder_name="resnet18", encoder_weights=None, in_channels=3, classes=1).to(device)
    opt = torch.optim.Adam(model.parameters(), 1e-3)
    x = torch.randn(8, 3, 256, 256, device=device)
    y = (torch.rand(8, 1, 256, 256, device=device) > 0.97).float()
    loss_fn = torch.nn.BCEWithLogitsLoss()

    def step():
        opt.zero_grad()
        loss_fn(model(x), y).backward()
        opt.step()
        if device == "cuda":
            torch.cuda.synchronize()

    step()
    t = time.time()
    for _ in range(3):
        step()
    per_img = (time.time() - t) / 24
    epoch = per_img * 150 * 1.3  # 150 фото train + проверка на valid + чтение файлов
    say(OK, "~%.0f мс на фото -> эпоха мини-датасета ~%.0f с, 8 эпох ~%.1f мин" % (per_img * 1000, epoch, epoch * 8 / 60))
    if epoch * 8 > 15 * 60:
        say(WARN, "Долго для занятия", "python tools/make_mini_dataset.py --train 80 --valid 20 --test 20")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="не скачивать веса, проверить кэш")
    ap.add_argument("--no-bench", action="store_true")
    a = ap.parse_args()
    os.chdir(ROOT)
    print("Проверка окружения практикума  (%s)" % ROOT)
    check_python()
    libs_ok = check_libs()
    device = "cpu"
    if libs_ok:
        device = check_gpu()
        check_weights(a.offline)
    check_data()
    check_apps()
    if libs_ok and not a.no_bench:
        bench(device)
    print("\n" + ("Всё готово к занятию." if not problems else "Нужно исправить:\n  - " + "\n  - ".join(problems)))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
