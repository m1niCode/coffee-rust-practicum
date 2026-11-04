# -*- coding: utf-8 -*-
"""Применение обученной модели к фотографиям. Логика перенесена из infer_rust.py."""
import cv2
import numpy as np
import segmentation_models_pytorch as smp
import torch

from .data import find_mask, read_mask

OVERLAY_ALPHA = 0.45
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


class RustModel:
    """Загруженная модель. threshold=None берёт порог, сохранённый вместе с моделью."""

    def __init__(self, model_path, threshold=None, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        ckpt = torch.load(model_path, map_location=self.device, weights_only=False)
        p = ckpt.get("params", {})
        self.arch = p.get("ARCH", "Unet")
        self.encoder = p.get("ENCODER", "resnet18")
        self.img_size = int(p.get("IMG_SIZE", 512))
        self.default_threshold = float(p.get("THRESHOLD", 0.5))
        self.threshold = float(threshold) if threshold is not None else self.default_threshold
        self.model = getattr(smp, self.arch)(encoder_name=self.encoder, encoder_weights=None, in_channels=3, classes=1)
        self.model.load_state_dict(ckpt["state"])
        self.model.to(self.device).eval()

    def predict_prob(self, img_rgb):
        """Карта вероятности ржавчины в размере исходного фото."""
        h, w = img_rgb.shape[:2]
        x = cv2.resize(img_rgb, (self.img_size, self.img_size), interpolation=cv2.INTER_LINEAR)
        x = (x.astype(np.float32) / 255 - MEAN) / STD
        x = torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            p = torch.sigmoid(self.model(x))[0, 0].cpu().numpy()
        return cv2.resize(p, (w, h), interpolation=cv2.INTER_LINEAR)


def make_overlay(img_rgb, mask, color=(255, 0, 0), alpha=OVERLAY_ALPHA):
    out = img_rgb.astype(np.float32).copy()
    col = np.array(color, np.float32)
    out[mask] = (1 - alpha) * out[mask] + alpha * col
    out = out.astype(np.uint8)
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(out, cnts, -1, color, max(1, img_rgb.shape[1] // 500))
    return out


def analyze(model, img_rgb, mask_path=None):
    """Один кадр: возвращает (запись с показателями, маска предсказания, оверлей RGB)."""
    h, w = img_rgb.shape[:2]
    prob = model.predict_prob(img_rgb)
    pred = prob > model.threshold
    rec = {
        "width": w, "height": h,
        "rust_pred_pct": round(float(pred.mean() * 100), 3),
        "rust_pred_pixels": int(pred.sum()),
        "mean_confidence": round(float(prob[pred].mean()), 3) if pred.any() else None,
        "max_probability": round(float(prob.max()), 3),
        "rust_true_pct": None, "diff_pct": None, "IoU": None, "Dice": None,
    }
    if mask_path:
        gt = read_mask(mask_path, (h, w)) > 0
        tp = int((pred & gt).sum()); fpx = int((pred & ~gt).sum()); fnx = int((~pred & gt).sum())
        rec["rust_true_pct"] = round(float(gt.mean() * 100), 3)
        rec["diff_pct"] = round(rec["rust_pred_pct"] - rec["rust_true_pct"], 3)
        den_i = tp + fpx + fnx
        rec["IoU"] = round(tp / den_i, 3) if den_i else 1.0
        den_d = 2 * tp + fpx + fnx
        rec["Dice"] = round(2 * tp / den_d, 3) if den_d else 1.0
    return rec, pred, make_overlay(img_rgb, pred)


__all__ = ["RustModel", "analyze", "make_overlay", "find_mask"]
