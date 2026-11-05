# -*- coding: utf-8 -*-
"""Разметка из labelme или Label Studio -> маски .png (0 — фон, 1 — ржавчина), как в датасете.

Результат — папка, готовая для обучения: рядом с каждой маской NAME_mask.png лежит фото NAME.jpg.

labelme (папка с .json, которые labelme сохраняет рядом с фото):
    python tools/annotations_to_masks.py practicum/label_set/images --out practicum/my_masks

Label Studio (Export -> JSON, файл project-1-at-....json):
    python tools/annotations_to_masks.py ~/Загрузки/project-1-at-2026.json \
        --images practicum/label_set/images --out practicum/my_masks

Понимает: labelme — polygon, rectangle, circle, mask (ИИ-разметка);
Label Studio — PolygonLabels, RectangleLabels, EllipseLabels, BrushLabels (кисть).
Учитываются все метки (класс один — rust); --label оставляет только указанную.
"""
import argparse
import base64
import glob
import io
import json
import os
import re
import shutil
import sys
from urllib.parse import parse_qs, unquote, urlparse

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.data import imread_u, imwrite_u  # noqa: E402

IMG_EXT = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")


# ---------------------------------------------------------------- labelme
def _b64_to_bool(b64):
    from PIL import Image
    return np.array(Image.open(io.BytesIO(base64.b64decode(b64)))).astype(bool)


def labelme_mask(doc, label=None):
    h, w = int(doc["imageHeight"]), int(doc["imageWidth"])
    mask = np.zeros((h, w), np.uint8)
    for sh in doc.get("shapes", []):
        if label and sh.get("label") != label:
            continue
        kind = sh.get("shape_type") or "polygon"
        pts = np.asarray(sh.get("points", []), np.float64)
        if kind == "polygon" and len(pts) >= 3:
            cv2.fillPoly(mask, [np.round(pts).astype(np.int32)], 1)
        elif kind == "rectangle" and len(pts) == 2:
            (x1, y1), (x2, y2) = np.round(pts).astype(int)
            cv2.rectangle(mask, (min(x1, x2), min(y1, y2)), (max(x1, x2), max(y1, y2)), 1, -1)
        elif kind == "circle" and len(pts) == 2:
            r = int(round(np.linalg.norm(pts[1] - pts[0])))
            cv2.circle(mask, tuple(np.round(pts[0]).astype(int)), r, 1, -1)
        elif kind == "mask" and sh.get("mask") and len(pts) == 2:
            part = _b64_to_bool(sh["mask"])
            x1, y1 = np.round(pts.min(axis=0)).astype(int)
            x1, y1 = max(x1, 0), max(y1, 0)
            ph, pw = min(part.shape[0], h - y1), min(part.shape[1], w - x1)
            mask[y1:y1 + ph, x1:x1 + pw][part[:ph, :pw]] = 1
        elif kind not in ("point", "line", "linestrip"):
            print("  ! пропущена фигура %s (%d точек)" % (kind, len(pts)))
    return mask


def read_labelme(paths, label):
    out = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        if "shapes" not in doc:
            continue
        name = os.path.basename(doc.get("imagePath") or os.path.splitext(p)[0] + ".jpg")
        out.append((name, labelme_mask(doc, label), os.path.dirname(p)))
    return out


# ---------------------------------------------------------------- Label Studio
def ls_file_name(url):
    """Имя исходного файла из ссылки Label Studio (загрузка через браузер или локальное хранилище)."""
    q = parse_qs(urlparse(url).query)
    path = q["d"][0] if "d" in q else urlparse(url).path
    name = os.path.basename(unquote(path))
    return re.sub(r"^[0-9a-f]{8}-", "", name)  # при загрузке в LS к имени добавляется префикс


def decode_ls_rle(rle):
    """RLE кисти Label Studio -> плоский массив RGBA uint8 (тот же формат, что label_studio_sdk.converter.brush).

    Заголовок: 32 бита — число значений, 5 бит — размер слова-1, 4×4 бита — длины счётчиков-1.
    Далее блоки: 1 бит (повтор/набор), 2 бита (какой счётчик), счётчик, затем слово(а).
    """
    bits = np.unpackbits(np.asarray(rle, dtype=np.uint8))
    pos = 0

    def read(n):
        nonlocal pos
        chunk = bits[pos:pos + n]
        pos += n
        return int("".join(map(str, chunk)), 2) if n else 0

    num = read(32)
    word = read(5) + 1
    sizes = [read(4) + 1 for _ in range(4)]
    out = np.zeros(num, np.uint8)
    i = 0
    while i < num:
        repeat = read(1)
        j = i + 1 + read(sizes[read(2)])
        if repeat:
            out[i:j] = read(word)
            i = j
        else:
            while i < j:
                out[i] = read(word)
                i += 1
    return out


def _decode_brush(rle, h, w):
    return np.reshape(decode_ls_rle(rle), (h, w, 4))[:, :, 3] > 0


def ls_mask(results, label=None):
    h = w = None
    for r in results:
        h, w = r.get("original_height", h), r.get("original_width", w)
    if not h:
        return None
    mask = np.zeros((h, w), np.uint8)
    for r in results:
        v, kind = r.get("value", {}), r.get("type", "")
        labels = v.get(kind) or v.get("polygonlabels") or v.get("brushlabels") or []
        if label and label not in labels:
            continue
        if "points" in v and kind != "keypointlabels":
            pts = np.asarray(v["points"], np.float64) * [w / 100.0, h / 100.0]
            if len(pts) >= 3:
                cv2.fillPoly(mask, [np.round(pts).astype(np.int32)], 1)
        elif kind == "brushlabels" or v.get("format") == "rle":
            mask[_decode_brush(v["rle"], h, w)] = 1
        elif kind == "rectanglelabels" or (kind == "" and "width" in v):
            x, y = v["x"] * w / 100, v["y"] * h / 100
            bw, bh = v["width"] * w / 100, v["height"] * h / 100
            c, s = np.cos(np.radians(v.get("rotation", 0))), np.sin(np.radians(v.get("rotation", 0)))
            corners = np.array([[0, 0], [bw, 0], [bw, bh], [0, bh]])  # поворот в LS — вокруг левого верхнего угла
            box = corners @ np.array([[c, s], [-s, c]]) + [x, y]
            cv2.fillPoly(mask, [np.round(box).astype(np.int32)], 1)
        elif kind == "ellipselabels":
            cv2.ellipse(mask, (int(v["x"] * w / 100), int(v["y"] * h / 100)),
                        (int(v["radiusX"] * w / 100), int(v["radiusY"] * h / 100)),
                        v.get("rotation", 0), 0, 360, 1, -1)
    return mask


def read_label_studio(tasks, label):
    out = []
    for t in tasks:
        if "annotations" in t:  # Export -> JSON
            url = next((x for x in t.get("data", {}).values() if isinstance(x, str)), "")
            anns = [a for a in t["annotations"] if not a.get("was_cancelled")]
            if not anns:
                continue
            anns.sort(key=lambda a: a.get("updated_at") or a.get("created_at") or "")
            results = anns[-1].get("result", [])
        else:  # Export -> JSON-MIN
            url = t.get("image", "")
            results = []
            for key, val in t.items():
                for item in (val if isinstance(val, list) else []):
                    if isinstance(item, dict) and "original_width" in item:
                        kind = next((k for k in item if k.endswith("labels")), key + "labels")
                        results.append({"type": kind, "value": item,
                                        "original_width": item["original_width"],
                                        "original_height": item["original_height"]})
        name = ls_file_name(url)
        m = ls_mask(results, label)
        if m is None:  # задача размечена «пусто» — лист здоров, размер берём из фото
            m = "empty"
        out.append((name, m, None))
    return out


# ---------------------------------------------------------------- main
def find_image(name, dirs):
    stem = os.path.splitext(name)[0]
    for d in dirs:
        if not d:
            continue
        for ext in IMG_EXT:
            p = os.path.join(d, stem + ext)
            if os.path.exists(p):
                return p
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="папка с .json labelme, один .json labelme или экспорт Label Studio (.json)")
    ap.add_argument("--images", default="", help="папка с исходными фото (если их нет рядом с разметкой)")
    ap.add_argument("--out", required=True, help="куда положить пары NAME.jpg + NAME_mask.png")
    ap.add_argument("--label", default=None, help="учитывать только эту метку (по умолчанию все)")
    a = ap.parse_args()

    if os.path.isdir(a.src):
        items = read_labelme(sorted(glob.glob(os.path.join(a.src, "*.json"))), a.label)
        fmt = "labelme"
    else:
        with open(a.src, encoding="utf-8") as f:
            doc = json.load(f)
        if isinstance(doc, list):
            items, fmt = read_label_studio(doc, a.label), "Label Studio"
        else:
            items, fmt = read_labelme([a.src], a.label), "labelme"
    if not items:
        sys.exit("Разметка не найдена в %s. Проверьте путь и что разметка сохранена." % a.src)

    os.makedirs(a.out, exist_ok=True)
    done = 0
    for name, mask, near in items:
        img = find_image(name, [near, a.images, os.path.dirname(os.path.abspath(a.src))])
        if isinstance(mask, str):  # пустая задача Label Studio
            if not img:
                print("  ! %s: нет фото, пустую маску не из чего построить" % name)
                continue
            mask = np.zeros(imread_u(img).shape[:2], np.uint8)
        stem = os.path.splitext(name)[0]
        if img:
            ih, iw = imread_u(img).shape[:2]
            if mask.shape != (ih, iw):
                print("  ! %s: размер разметки %s не совпадает с фото %s — маска растянута" % (name, mask.shape, (ih, iw)))
                mask = cv2.resize(mask, (iw, ih), interpolation=cv2.INTER_NEAREST)
            dst = os.path.join(a.out, stem + os.path.splitext(img)[1].lower().replace(".jpeg", ".jpg"))
            if os.path.abspath(img) != os.path.abspath(dst):
                shutil.copyfile(img, dst)
        else:
            print("  ! %s: фото не найдено, сохранена только маска (укажите --images)" % name)
        imwrite_u(os.path.join(a.out, stem + "_mask.png"), mask)
        print("  %-28s ржавчина %5.2f%%  пятен %d" % (stem, mask.mean() * 100, cv2.connectedComponents(mask)[0] - 1))
        done += 1
    print("Формат: %s. Готово масок: %d -> %s" % (fmt, done, a.out))


if __name__ == "__main__":
    main()
