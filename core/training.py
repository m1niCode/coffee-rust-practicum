# -*- coding: utf-8 -*-
"""Обучение модели сегментации (U-Net и др.). Алгоритм перенесён из train_gui.py без изменений:
интерфейс общается с ним только через очередь событий q и флаг остановки stop.

События в q: ("log", str), ("progress", 0..1), ("epoch", dict), ("done", путь), ("error", текст).
"""
import json
import os
import random
import time
import traceback

import albumentations as A
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import segmentation_models_pytorch as smp
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from .data import find_pairs, imread_u, imwrite_u, read_mask


class RustDataset(Dataset):
    def __init__(self, pairs, train, img_size, aug):
        self.pairs = pairs
        tf = [A.Resize(img_size, img_size)]
        if train:
            if aug["flip"]:
                tf += [A.HorizontalFlip(p=0.5), A.VerticalFlip(p=0.5)]
            if aug["rot"]:
                tf += [A.RandomRotate90(p=0.5)]
            if aug["bright"]:
                tf += [A.RandomBrightnessContrast(p=0.5)]
        self.tf = A.Compose(tf)
        self.mean = np.array([0.485, 0.456, 0.406], np.float32)
        self.std = np.array([0.229, 0.224, 0.225], np.float32)

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, i):
        ip, mp = self.pairs[i]
        img = cv2.cvtColor(imread_u(ip), cv2.COLOR_BGR2RGB)
        if mp:
            mask = read_mask(mp)
            if mask.shape[:2] != img.shape[:2]:
                mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
        else:
            mask = np.zeros(img.shape[:2], np.float32)
        out = self.tf(image=img, mask=mask)
        x = (out["image"].astype(np.float32) / 255 - self.mean) / self.std
        return torch.from_numpy(x.transpose(2, 0, 1)), torch.from_numpy(out["mask"]).unsqueeze(0).float()

def iou_dice(tp, fp, fn, eps=1e-7):
    return (tp + eps) / (tp + fp + fn + eps), (2 * tp + eps) / (2 * tp + fp + fn + eps)

# ======================================================================
#                 ОБУЧЕНИЕ (работает в отдельном потоке)
# ======================================================================
def train_worker(cfg, q, stop):
    """Обучение. q - любой объект с методом put((вид, данные)); stop - threading.Event."""
    log = lambda s: q.put(("log", s))
    try:
        random.seed(cfg["seed"]); np.random.seed(cfg["seed"]); torch.manual_seed(cfg["seed"])
        device = "cuda" if (cfg["device"] == "auto" and torch.cuda.is_available()) else "cpu"
        log("Устройство вычислений: " + ("видеокарта (GPU)" if device == "cuda" else "процессор (CPU)"))

        train_pairs = find_pairs(cfg["train_dir"])
        valid_pairs = find_pairs(cfg["valid_dir"])
        test_pairs = find_pairs(cfg["test_dir"], need_mask=False) if cfg["test_dir"] else []
        log("Найдено снимков: train %d, valid %d, test %d" % (len(train_pairs), len(valid_pairs), len(test_pairs)))
        if not train_pairs or not valid_pairs:
            raise RuntimeError("В папках train/valid не найдены пары «фото .jpg + маска .png».")

        base = os.path.join(cfg["out_dir"], cfg["run_name"])
        run_dir, n = base, 1
        while os.path.exists(run_dir):
            n += 1
            run_dir = "%s_%d" % (base, n)
        os.makedirs(run_dir)
        log("Папка результатов: " + run_dir)

        aug = cfg["aug"]
        tr_ds = RustDataset(train_pairs, True, cfg["img_size"], aug)
        va_ds = RustDataset(valid_pairs, False, cfg["img_size"], aug)
        train_dl = DataLoader(tr_ds, batch_size=cfg["batch"], shuffle=True, num_workers=0)
        valid_dl = DataLoader(va_ds, batch_size=cfg["batch"], shuffle=False, num_workers=0)

        share = np.mean([read_mask(m).mean() for _, m in train_pairs])
        log("Средняя доля ржавчины в масках train: %.2f%% пикселей" % (share * 100))

        def make_model(weights):
            return getattr(smp, cfg["arch"])(encoder_name=cfg["encoder"], encoder_weights=weights,
                                             in_channels=3, classes=1)
        weights = "imagenet" if cfg["pretrained"] else None
        try:
            model = make_model(weights)
        except Exception as e:
            log("Не удалось загрузить предобученные веса (%s). Обучение продолжится без них." % type(e).__name__)
            cfg["pretrained"] = False
            model = make_model(None)
        model.to(device)

        bce = nn.BCEWithLogitsLoss()
        dice = smp.losses.DiceLoss(mode="binary", from_logits=True)
        dw, thr = cfg["dice_w"], cfg["thr"]
        loss_fn = lambda lg, y: (1 - dw) * bce(lg, y) + dw * dice(lg, y)

        opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"])
        sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=2)

        params = dict(ARCH=cfg["arch"], ENCODER=cfg["encoder"], PRETRAINED=cfg["pretrained"],
                      IMG_SIZE=cfg["img_size"], EPOCHS=cfg["epochs"], BATCH_SIZE=cfg["batch"],
                      LR=cfg["lr"], AUGMENT=bool(any(aug.values())), AUG_FLIP=aug["flip"],
                      AUG_ROT90=aug["rot"], AUG_BRIGHT=aug["bright"], DICE_WEIGHT=dw,
                      THRESHOLD=thr, SEED=cfg["seed"], PATIENCE=cfg["patience"])
        with open(os.path.join(run_dir, "params.json"), "w", encoding="utf-8") as f:
            json.dump(dict(params, train_dir=cfg["train_dir"], valid_dir=cfg["valid_dir"],
                           test_dir=cfg["test_dir"]), f, indent=2, ensure_ascii=False)

        E = cfg["epochs"]
        logrows, best_iou, bad, t0 = [], -1.0, 0, time.time()
        nb = max(1, len(train_dl))
        for ep in range(1, E + 1):
            if stop.is_set():
                break
            model.train(); tr_loss = 0.0
            for bi, (x, y) in enumerate(train_dl):
                if stop.is_set():
                    break
                x, y = x.to(device), y.to(device)
                opt.zero_grad()
                loss = loss_fn(model(x), y)
                loss.backward(); opt.step()
                tr_loss += loss.item() * len(x)
                q.put(("progress", ((ep - 1) + (bi + 1) / nb) / E))
            if stop.is_set():
                break
            tr_loss /= len(train_dl.dataset)

            model.eval(); va_loss = 0.0; TP = FP = FN = 0.0
            with torch.no_grad():
                for x, y in valid_dl:
                    x, y = x.to(device), y.to(device)
                    lg = model(x)
                    va_loss += loss_fn(lg, y).item() * len(x)
                    p = (torch.sigmoid(lg) > thr).float()
                    TP += (p * y).sum().item(); FP += (p * (1 - y)).sum().item(); FN += ((1 - p) * y).sum().item()
            va_loss /= len(valid_dl.dataset)
            iou, dsc = iou_dice(TP, FP, FN)
            sched.step(va_loss)
            row = dict(epoch=ep, train_loss=tr_loss, val_loss=va_loss, val_iou=iou, val_dice=dsc)
            logrows.append(row)
            mark = ""
            if iou > best_iou:
                best_iou, bad, mark = iou, 0, "  <- лучшая"
                torch.save({"state": model.state_dict(), "params": params}, os.path.join(run_dir, "best_model.pth"))
            else:
                bad += 1
            el = time.time() - t0
            log("Эпоха %d/%d | потери train %.4f, valid %.4f | IoU %.3f | Dice %.3f%s | осталось ~%.1f мин"
                % (ep, E, tr_loss, va_loss, iou, dsc, mark, el / ep * (E - ep) / 60))
            q.put(("epoch", row))
            if cfg["patience"] > 0 and bad >= cfg["patience"]:
                log("Ранняя остановка: качество не росло %d эпох подряд." % bad)
                break

        if stop.is_set():
            log("Обучение остановлено пользователем.")
        if not logrows:
            q.put(("done", run_dir)); return

        df = pd.DataFrame(logrows)
        df.to_csv(os.path.join(run_dir, "metrics.csv"), index=False)
        log("Обучение завершено за %.1f мин. Лучший IoU на valid: %.3f" % ((time.time() - t0) / 60, best_iou))

        fig, ax = plt.subplots(1, 2, figsize=(11, 4))
        ax[0].plot(df.epoch, df.train_loss, label="train"); ax[0].plot(df.epoch, df.val_loss, label="valid")
        ax[0].set_title("Потери (меньше - лучше)"); ax[0].set_xlabel("Эпоха"); ax[0].legend()
        ax[1].plot(df.epoch, df.val_iou, label="IoU"); ax[1].plot(df.epoch, df.val_dice, label="Dice")
        ax[1].set_title("Качество на valid (больше - лучше)"); ax[1].set_xlabel("Эпоха"); ax[1].legend()
        fig.tight_layout(); fig.savefig(os.path.join(run_dir, "curves.png"), dpi=120); plt.close(fig)

        ckpt = torch.load(os.path.join(run_dir, "best_model.pth"), map_location=device, weights_only=False)
        model.load_state_dict(ckpt["state"]); model.eval()

        def predict(x):
            with torch.no_grad():
                return torch.sigmoid(model(x.unsqueeze(0).to(device)))[0, 0].cpu().numpy()

        if test_pairs:
            log("Оценка лучшей модели на тестовой выборке...")
            tdir = os.path.join(run_dir, "test_predictions"); os.makedirs(tdir, exist_ok=True)
            ds = RustDataset(test_pairs, False, cfg["img_size"], aug)
            rows, T = [], [0, 0, 0]
            for i, (ip, mp) in enumerate(test_pairs):
                x, y = ds[i]
                p = predict(x) > thr
                name = os.path.splitext(os.path.basename(ip))[0]
                imwrite_u(os.path.join(tdir, name + "_pred.png"), (p * 255).astype(np.uint8))
                r = {"file": os.path.basename(ip), "rust_pred_%": round(float(p.mean() * 100), 2)}
                if mp:
                    g = y[0].numpy() > 0.5
                    tp, fp, fn = int((p & g).sum()), int((p & ~g).sum()), int((~p & g).sum())
                    r["rust_true_%"] = round(float(g.mean() * 100), 2)
                    r["IoU"], r["Dice"] = [round(float(v), 3) for v in iou_dice(tp, fp, fn)]
                    T[0] += tp; T[1] += fp; T[2] += fn
                rows.append(r)
            pd.DataFrame(rows).to_csv(os.path.join(run_dir, "test_results.csv"), index=False, encoding="utf-8-sig")
            if any(mp for _, mp in test_pairs):
                it, dt = iou_dice(*T)
                log("ТЕСТ: IoU %.3f | Dice %.3f" % (it, dt))
                with open(os.path.join(run_dir, "test_summary.json"), "w") as f:
                    json.dump({"IoU": float(it), "Dice": float(dt), "n_images": len(test_pairs)}, f, indent=2)

        def save_examples(pairs, fname, n=6):
            ds_ = RustDataset(pairs, False, cfg["img_size"], aug)
            n = min(n, len(ds_))
            fig, axs = plt.subplots(n, 3, figsize=(9, 3 * n), squeeze=False)
            for i in range(n):
                x, y = ds_[i]
                p = predict(x) > thr
                img = np.clip(x.numpy().transpose(1, 2, 0) * ds_.std + ds_.mean, 0, 1)
                hm = pairs[i][1] is not None
                items = [(img, "Фото"), (y[0].numpy() if hm else np.zeros_like(p), "Разметка" if hm else "Разметки нет"),
                         (p, "Модель: %.1f%% поражения" % (p.mean() * 100))]
                for j, (im, t) in enumerate(items):
                    axs[i, j].imshow(im, cmap=None if j == 0 else "gray"); axs[i, j].set_title(t, fontsize=9); axs[i, j].axis("off")
            fig.tight_layout(); fig.savefig(os.path.join(run_dir, fname), dpi=100); plt.close(fig)

        save_examples(valid_pairs, "examples_valid.png")
        if test_pairs:
            save_examples(test_pairs, "examples_test.png")
        log("Готово. Все результаты сохранены в: " + run_dir)
        q.put(("done", run_dir))
    except Exception:
        q.put(("error", traceback.format_exc()))
