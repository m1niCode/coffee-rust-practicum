# -*- coding: utf-8 -*-
"""Работа с данными: чтение файлов, поиск пар «фото + маска», проверка папок.

Код перенесён из train_gui.py / infer_rust.py без изменения алгоритмов.
"""
import glob
import os

import cv2
import numpy as np


def imread_u(path, flags=cv2.IMREAD_COLOR):
    """Чтение файла, устойчивое к русским буквам в пути."""
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), flags)


def imwrite_u(path, img):
    ok, buf = cv2.imencode(os.path.splitext(path)[1], img)
    if not ok:
        raise IOError("Не удалось сохранить: " + path)
    buf.tofile(path)


def find_mask(img_path):
    stem = os.path.splitext(img_path)[0]
    for cand in (stem + ".png", stem + "_mask.png"):
        if os.path.exists(cand):
            return cand
    return None


def find_pairs(folder, need_mask=True):
    """Список (фото, маска). Если need_mask=False, снимки без маски тоже попадают в список."""
    files = []
    for ext in ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG"):
        files += glob.glob(os.path.join(folder, ext))
    pairs = []
    for img in sorted(set(files)):
        mask = find_mask(img)
        if mask or not need_mask:
            pairs.append((img, mask))
    return pairs


def read_mask(path, shape_hw=None):
    """Маска как массив float32 (0/1). Если задан shape_hw, маска приводится к этому размеру."""
    m = imread_u(path, cv2.IMREAD_UNCHANGED)
    if m.ndim == 3:
        m = m[..., 0]
    if shape_hw is not None and m.shape[:2] != tuple(shape_hw):
        m = cv2.resize(m, (shape_hw[1], shape_hw[0]), interpolation=cv2.INTER_NEAREST)
    return (m > 0).astype(np.float32)


def check_folders(train_dir, valid_dir, test_dir=""):
    """Проверка папок для экрана «Данные». Возвращает словарь со статусами, а не текст."""
    def folder_info(path, need_mask):
        if not path or not os.path.isdir(path):
            return {"exists": False, "photos": 0, "pairs": 0}
        pairs = find_pairs(path, need_mask=False)
        return {"exists": True, "photos": len(pairs), "pairs": sum(1 for _, m in pairs if m),
                "pairs_list": pairs}

    tr, va = folder_info(train_dir, True), folder_info(valid_dir, True)
    te = folder_info(test_dir, False) if test_dir and test_dir.strip() else {"exists": False, "photos": 0, "pairs": 0}

    rust_share = None
    if tr["pairs"]:
        sample = [m for _, m in tr["pairs_list"] if m][:100]
        rust_share = float(np.mean([read_mask(m).mean() for m in sample]))

    duplicates = []
    if tr["pairs"] and va["pairs"]:
        a = {os.path.basename(p) for p, _ in tr["pairs_list"]}
        b = {os.path.basename(p) for p, _ in va["pairs_list"]}
        duplicates = sorted(a & b)

    for d in (tr, va, te):
        d.pop("pairs_list", None)
    return {
        "train": tr, "valid": va, "test": te,
        "rust_share_train": rust_share,
        "duplicates": duplicates[:20], "duplicates_count": len(duplicates),
        "ok": bool(tr["pairs"] and va["pairs"]),
    }
