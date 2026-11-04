# -*- coding: utf-8 -*-
"""Чтение результатов уже проведённых экспериментов из папки OUT/<имя>/.

Работает на стандартной библиотеке, поэтому не требует torch и быстро открывает экран «Результаты».
"""
import csv
import glob
import json
import os


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _read_metrics(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return []
    out = []
    for r in rows:
        try:
            out.append({k: float(r[k]) for k in ("train_loss", "val_loss", "val_iou", "val_dice")})
        except (KeyError, ValueError):
            continue
    return out


def model_file(run_dir):
    """Файл лучшей модели в папке эксперимента (best_model*.pth) или None."""
    found = sorted(glob.glob(os.path.join(run_dir, "*.pth")))
    return found[0] if found else None


def load_experiment(out_dir, name):
    run_dir = os.path.join(out_dir, name)
    params = _read_json(os.path.join(run_dir, "params.json"))
    if params is None or not os.path.isdir(run_dir):
        return None
    metrics = _read_metrics(os.path.join(run_dir, "metrics.csv"))
    test = _read_json(os.path.join(run_dir, "test_summary.json")) or {}
    return {
        "id": name,
        "arch": params.get("ARCH", "Unet"),
        "encoder": params.get("ENCODER", "resnet18"),
        "image_size": params.get("IMG_SIZE"),
        "epochs_planned": params.get("EPOCHS"),
        "epochs_done": len(metrics),
        "batch": params.get("BATCH_SIZE"),
        "lr": params.get("LR"),
        "threshold": params.get("THRESHOLD", 0.5),
        "test_iou": test.get("IoU"),
        "test_dice": test.get("Dice"),
        "test_images": test.get("n_images"),
        "best_val_iou": max((m["val_iou"] for m in metrics), default=None),
        "curves": {
            "val_iou": [m["val_iou"] for m in metrics],
            "train_loss": [m["train_loss"] for m in metrics],
            "val_loss": [m["val_loss"] for m in metrics],
        },
        "has_model": model_file(run_dir) is not None,
        "modified": os.path.getmtime(run_dir),
    }


def list_experiments(out_dir):
    if not os.path.isdir(out_dir):
        return []
    items = []
    for name in sorted(os.listdir(out_dir)):
        e = load_experiment(out_dir, name)
        if e:
            items.append(e)
    return items
