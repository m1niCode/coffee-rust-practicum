# -*- coding: utf-8 -*-
"""Облегчённый датасет для обучения на занятии (несколько минут вместо часа).

Берёт часть train/valid/test так, чтобы доля поражения была представлена равномерно,
исключает фото-источники листьев из practicum/label_set (их размечают участники)
и может добавить в train папки с разметкой участников (--extra).

    python tools/make_mini_dataset.py                                   # 150 / 40 / 40
    python tools/make_mini_dataset.py --extra practicum/my_masks        # + листья, размеченные на занятии
    python tools/make_mini_dataset.py --train 300 --out practicum/data_mid
"""
import argparse
import csv
import glob
import os
import re
import shutil
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.data import find_pairs, read_mask  # noqa: E402


def source_id(path):
    """Исходный снимок: несколько листьев одного фото (…_obj0, _obj1) — один источник."""
    return re.split(r"_(?:obj|leaf)\d+|_(?:png|jpg)\.rf", os.path.basename(path))[0]


def pick(pairs, n, seed):
    """n пар, равномерно по доле поражения (здоровые листья тоже попадают)."""
    if n >= len(pairs):
        return list(pairs)
    shares = np.array([read_mask(m).mean() for _, m in pairs])
    order = np.argsort(shares, kind="stable")
    rng = np.random.default_rng(seed)
    bins = np.array_split(order, n)
    return [pairs[int(rng.choice(b))] for b in bins]


def copy_pairs(pairs, dst):
    os.makedirs(dst, exist_ok=True)
    for img, mask in pairs:
        stem = os.path.splitext(os.path.basename(img))[0]
        shutil.copyfile(img, os.path.join(dst, stem + ".jpg"))
        shutil.copyfile(mask, os.path.join(dst, stem + "_mask.png"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=ROOT, help="где лежат полные train/ valid/ test/")
    ap.add_argument("--out", default=os.path.join(ROOT, "practicum", "data_mini"))
    ap.add_argument("--train", type=int, default=150)
    ap.add_argument("--valid", type=int, default=40)
    ap.add_argument("--test", type=int, default=40)
    ap.add_argument("--extra", nargs="*", default=[], help="папки с разметкой участников -> в train")
    ap.add_argument("--label-set", default=os.path.join(ROOT, "practicum", "label_set", "label_set.csv"))
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    excluded = set()
    if os.path.exists(a.label_set):
        with open(a.label_set, encoding="utf-8-sig") as f:
            excluded = {source_id(r["source_file"]) for r in csv.DictReader(f)}

    parts = {}
    for split, n in (("train", a.train), ("valid", a.valid), ("test", a.test)):
        pairs = [p for p in find_pairs(os.path.join(a.data, split)) if source_id(p[0]) not in excluded]
        parts[split] = pick(pairs, n, a.seed)

    shutil.rmtree(a.out, ignore_errors=True)
    for split, pairs in parts.items():
        copy_pairs(pairs, os.path.join(a.out, split))

    added = 0
    for d in a.extra:
        extra = find_pairs(d)
        copy_pairs(extra, os.path.join(a.out, "train"))
        added += len(extra)
        print("  + %d размеченных листьев из %s" % (len(extra), d))

    print("Готово: %s" % a.out)
    for split, pairs in parts.items():
        share = np.mean([read_mask(m).mean() for _, m in pairs]) * 100
        extra = " (+%d своих)" % added if split == "train" and added else ""
        print("  %-5s %3d снимков%s, средняя доля ржавчины %.2f%%" % (split, len(pairs), extra, share))
    if excluded:
        print("  исключены фото-источники листьев для разметки: %d" % len(excluded))


if __name__ == "__main__":
    main()
