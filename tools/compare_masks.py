# -*- coding: utf-8 -*-
"""Сравнение ручной разметки с эталоном: IoU, Dice, доля поражения и картинка-наложение.

    python tools/compare_masks.py practicum/my_masks
    python tools/compare_masks.py practicum/my_masks --ref practicum/label_set/reference --out practicum/compare

На наложении: жёлтое — совпало, зелёное — есть только в эталоне (пропущено),
красное — есть только у вас (лишнее).
"""
import argparse
import csv
import glob
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.data import imread_u, imwrite_u, read_mask  # noqa: E402

COLORS = {"both": (0, 220, 255), "ref": (0, 200, 0), "mine": (0, 0, 255)}  # BGR


def overlay(img, mine, ref, alpha=0.55):
    out = img.astype(np.float32)
    for key, m in (("both", mine & ref), ("ref", ref & ~mine), ("mine", mine & ~ref)):
        out[m] = (1 - alpha) * out[m] + alpha * np.array(COLORS[key], np.float32)
    return out.astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mine", help="папка с вашими масками NAME_mask.png (и фото NAME.jpg)")
    ap.add_argument("--ref", default=os.path.join(ROOT, "practicum", "label_set", "reference"))
    ap.add_argument("--images", default=os.path.join(ROOT, "practicum", "label_set", "images"))
    ap.add_argument("--out", default="", help="куда сохранить наложения и таблицу (по умолчанию <mine>/compare)")
    a = ap.parse_args()

    out_dir = a.out or os.path.join(a.mine, "compare")
    os.makedirs(out_dir, exist_ok=True)
    rows, T = [], np.zeros(3)
    for mp in sorted(glob.glob(os.path.join(a.mine, "*_mask.png"))):
        stem = os.path.basename(mp)[:-len("_mask.png")]
        rp = os.path.join(a.ref, stem + "_mask.png")
        if not os.path.exists(rp):
            print("  ? %s: эталона нет, пропускаю" % stem)
            continue
        ref = read_mask(rp) > 0
        mine = read_mask(mp, ref.shape) > 0
        tp, fp, fn = int((mine & ref).sum()), int((mine & ~ref).sum()), int((~mine & ref).sum())
        T += (tp, fp, fn)
        iou = tp / (tp + fp + fn) if tp + fp + fn else 1.0
        dice = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1.0
        r = {"name": stem, "mine_pct": round(mine.mean() * 100, 2), "ref_pct": round(ref.mean() * 100, 2),
             "IoU": round(iou, 3), "Dice": round(dice, 3)}
        rows.append(r)
        print("  %-12s вы %5.2f%%  эталон %5.2f%%  IoU %.3f  Dice %.3f" % (stem, r["mine_pct"], r["ref_pct"], iou, dice))
        img_p = next((p for p in (os.path.join(a.mine, stem + ".jpg"), os.path.join(a.images, stem + ".jpg"))
                      if os.path.exists(p)), None)
        img = imread_u(img_p) if img_p else np.full(ref.shape + (3,), 40, np.uint8)
        if img.shape[:2] != ref.shape:
            img = cv2.resize(img, (ref.shape[1], ref.shape[0]))
        imwrite_u(os.path.join(out_dir, stem + "_compare.jpg"), np.hstack([img, overlay(img, mine, ref)]))
    if not rows:
        sys.exit("Не найдено ни одной пары «ваша маска + эталон». Проверьте имена файлов (leaf_01_mask.png …).")
    tp, fp, fn = T
    iou, dice = tp / (tp + fp + fn), 2 * tp / (2 * tp + fp + fn)
    with open(os.path.join(out_dir, "compare.csv"), "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print("ИТОГО по %d листьям: IoU %.3f, Dice %.3f. Наложения: %s" % (len(rows), iou, dice, out_dir))
    print("Цвета: жёлтый — совпало, зелёный — пропущено, красный — лишнее.")


if __name__ == "__main__":
    main()
