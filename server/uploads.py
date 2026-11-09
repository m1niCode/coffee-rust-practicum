# -*- coding: utf-8 -*-
"""Приём данных от пользователя: отдельные фото/маски или zip-архив с ними."""
import os
import shutil
import zipfile

from fastapi import HTTPException

from . import config
from .security import KINDS, data_dir, dir_size, ws_root

ALLOWED_EXT = (".jpg", ".jpeg", ".png")
_KIND_ALIASES = {"train": "train", "valid": "valid", "val": "valid", "validation": "valid", "test": "test"}


def _clean_name(name):
    base = os.path.basename(name.replace("\\", "/"))
    base = "".join(ch for ch in base if ch >= " " and ch not in '<>:"|?*')
    return base[:150]


def _kind_from_path(parts):
    for p in parts[:-1]:
        k = _KIND_ALIASES.get(p.lower())
        if k:
            return k
    return None


class _Budget:
    """Следит, чтобы запрос не превысил лимиты: на один запрос и на всё пространство пользователя."""

    def __init__(self, ws):
        self.left_request = config.MAX_UPLOAD
        self.left_ws = config.MAX_WORKSPACE - dir_size(ws_root(ws))

    def take(self, n):
        self.left_request -= n
        self.left_ws -= n
        if self.left_request < 0:
            raise HTTPException(413, "Слишком большая загрузка (больше %d МБ). Разбейте её на части." % (config.MAX_UPLOAD // 2**20))
        if self.left_ws < 0:
            raise HTTPException(413, "Не хватает места в вашем рабочем пространстве. Удалите ненужные данные.")


def _write(stream, dest, budget):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as out:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            budget.take(len(chunk))
            out.write(chunk)


def save_uploads(ws, kind, uploads):
    """uploads: список (имя файла, файловый объект). kind: train|valid|test|auto.

    auto раскладывает файлы по папкам train/valid/test, как они названы внутри архива.
    Возвращает количество сохранённых файлов по папкам и число пропущенных.
    """
    if kind != "auto" and kind not in KINDS:
        raise HTTPException(422, "Неизвестная папка данных.")
    budget = _Budget(ws)
    saved = {k: 0 for k in KINDS}
    skipped = 0

    def put(path_parts, stream):
        nonlocal skipped
        base = _clean_name(path_parts[-1])
        target = kind if kind != "auto" else _kind_from_path(path_parts)
        if (not base or base.startswith(".") or not base.lower().endswith(ALLOWED_EXT)
                or target is None or any(p.startswith(("__MACOSX", ".")) for p in path_parts)):
            skipped += 1
            return
        _write(stream, os.path.join(data_dir(ws, target), base), budget)
        saved[target] += 1

    for name, fobj in uploads:
        if name.lower().endswith(".zip"):
            try:
                zf = zipfile.ZipFile(fobj)
            except zipfile.BadZipFile:
                raise HTTPException(422, "Архив %s повреждён или это не zip." % name)
            with zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    parts = [p for p in info.filename.replace("\\", "/").split("/") if p]
                    if not parts:
                        continue
                    with zf.open(info) as src:
                        put(parts, src)
        else:
            put([name], fobj)

    if not any(saved.values()):
        if kind == "auto":
            raise HTTPException(422, "В архиве нет фото и масок в папках train, valid или test.")
        raise HTTPException(422, "Нет файлов .jpg или .png. Загрузите фото, маски или zip-архив с ними.")
    return {"saved": saved, "skipped": skipped}


def clear_kind(ws, kind):
    if kind not in KINDS:
        raise HTTPException(422, "Неизвестная папка данных.")
    shutil.rmtree(data_dir(ws, kind), ignore_errors=True)
