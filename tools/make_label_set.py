# -*- coding: utf-8 -*-
"""Набор листьев для ручной разметки на практикуме.

Берёт из train листья с умеренным числом пятен (чтобы разметка одного листа занимала 2–4 минуты),
копирует фото под короткими именами leaf_01.jpg … и кладёт эталонные маски отдельно.

    python tools/make_label_set.py                      # 10 листьев из train/
    python tools/make_label_set.py --n 12 --out practicum/label_set
"""
import argparse
import csv
import glob
import os
import shutil
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.data import find_mask, imread_u, imwrite_u  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=os.path.join(ROOT, "train"), help="папка с фото и масками")
    ap.add_argument("--out", default=os.path.join(ROOT, "practicum", "label_set"))
    ap.add_argument("--n", type=int, default=10, help="сколько листьев отобрать")
    ap.add_argument("--min-spots", type=int, default=3)
    ap.add_argument("--max-spots", type=int, default=12)
    a = ap.parse_args()

    cands = []
    for img in sorted(glob.glob(os.path.join(a.src, "*.jpg"))):
        mp = find_mask(img)
        if not mp:
            continue
        m = imread_u(mp, cv2.IMREAD_UNCHANGED)
        h, w = imread_u(img).shape[:2]
        if m.shape[:2] != (h, w):
            continue
        b = (m > 0).astype(np.uint8)
        spots = cv2.connectedComponents(b)[0] - 1
        share = float(b.mean() * 100)
        if a.min_spots <= spots <= a.max_spots and 0.5 <= share <= 10:
            cands.append((share, spots, img, mp))
    if len(cands) < a.n:
        sys.exit("Подходящих листьев только %d, нужно %d. Ослабьте --min-spots/--max-spots." % (len(cands), a.n))

    # Равномерно по доле поражения: от слабого к сильному
    cands.sort()
    pick = [cands[int(i)] for i in np.linspace(0, len(cands) - 1, a.n)]

    img_dir, ref_dir = os.path.join(a.out, "images"), os.path.join(a.out, "reference")
    for d in (img_dir, ref_dir):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    rows = []
    for i, (share, spots, img, mp) in enumerate(pick, 1):
        name = "leaf_%02d" % i
        shutil.copyfile(img, os.path.join(img_dir, name + ".jpg"))
        m = (imread_u(mp, cv2.IMREAD_UNCHANGED) > 0).astype(np.uint8)
        imwrite_u(os.path.join(ref_dir, name + "_mask.png"), m)
        rows.append({"name": name, "source_file": os.path.basename(img),
                     "rust_pct": round(share, 2), "spots": spots})
    with open(os.path.join(a.out, "label_set.csv"), "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print("Отобрано %d листьев -> %s" % (len(rows), a.out))
    for r in rows:
        print("  %(name)s  ржавчина %(rust_pct)5.2f%%  пятен %(spots)2d" % r)


if __name__ == "__main__":
    main()
