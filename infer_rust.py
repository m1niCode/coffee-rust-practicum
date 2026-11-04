# -*- coding: utf-8 -*-
"""
Инференс модели сегментации ржавчины + окно просмотра результатов.

Что нужно рядом со скриптом (одна папка):
    infer_rust.py        - этот скрипт
    best_model.pth       - обученная модель (из OUT/exp1/best_model.pth)
    test/                - папка с тестовыми фото (*.jpg), маски *.png необязательны

Результаты сохраняются в папку OUT_test (создаётся автоматически):
    OUT_test/masks/      - маски предсказаний (белое = ржавчина)
    OUT_test/overlays/   - фото с наложенным контуром поражения
    OUT_test/results.csv - таблица параметров по каждому кадру
    OUT_test/summary.json- итоговые показатели
"""
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"            # обход конфликта OpenMP в Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# %% ============ ПАРАМЕТРЫ ============
MODEL_FILE    = "best_model_3.pth"   # имя файла модели (лежит рядом со скриптом)
TEST_DIR_NAME = "test"             # папка с тестовыми фото
OUT_DIR_NAME  = "OUT_test"         # папка результатов
THRESHOLD     = None               # None = взять порог из модели; или число 0.1-0.9
OVERLAY_ALPHA = 0.45               # прозрачность закраски поражения на картинке
PANEL_MAX     = 420                # максимальный размер одной картинки в окне (пикселей)

# %% ============ ИМПОРТЫ ============
import glob, json
import numpy as np
import cv2
import pandas as pd
import torch
import segmentation_models_pytorch as smp
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

TEST_DIR = os.path.join(BASE_DIR, TEST_DIR_NAME)
OUT_DIR  = os.path.join(BASE_DIR, OUT_DIR_NAME)
MASK_DIR = os.path.join(OUT_DIR, "masks")
OVL_DIR  = os.path.join(OUT_DIR, "overlays")
for d in (OUT_DIR, MASK_DIR, OVL_DIR):
    os.makedirs(d, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print("Устройство:", DEVICE)
print("Папка скрипта:", BASE_DIR)

# %% ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============
def imread_u(path, flags=cv2.IMREAD_COLOR):
    """Чтение файла, устойчивое к русским буквам в пути."""
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, flags)

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

def read_mask(path, shape_hw):
    m = imread_u(path, cv2.IMREAD_UNCHANGED)
    if m.ndim == 3:
        m = m[..., 0]
    if m.shape[:2] != tuple(shape_hw):
        m = cv2.resize(m, (shape_hw[1], shape_hw[0]), interpolation=cv2.INTER_NEAREST)
    return m > 0

def make_overlay(img_rgb, mask, color, alpha=OVERLAY_ALPHA):
    out = img_rgb.astype(np.float32).copy()
    col = np.array(color, np.float32)
    out[mask] = (1 - alpha) * out[mask] + alpha * col
    out = out.astype(np.uint8)
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(out, cnts, -1, color, max(1, img_rgb.shape[1] // 500))
    return out

# %% ============ ЗАГРУЗКА МОДЕЛИ ============
model_path = os.path.join(BASE_DIR, MODEL_FILE)
if not os.path.exists(model_path):
    found = sorted(glob.glob(os.path.join(BASE_DIR, "*.pth")))
    if not found:
        raise FileNotFoundError("Модель не найдена. Положите %s рядом со скриптом: %s" % (MODEL_FILE, BASE_DIR))
    model_path = found[0]
print("Модель:", model_path)

ckpt = torch.load(model_path, map_location=DEVICE, weights_only=False)
P = ckpt.get("params", {})
ARCH     = P.get("ARCH", "Unet")
ENCODER  = P.get("ENCODER", "resnet18")
IMG_SIZE = int(P.get("IMG_SIZE", 512))
THR      = float(THRESHOLD if THRESHOLD is not None else P.get("THRESHOLD", 0.5))

model = getattr(smp, ARCH)(encoder_name=ENCODER, encoder_weights=None, in_channels=3, classes=1)
model.load_state_dict(ckpt["state"])
model.to(DEVICE).eval()
print("Архитектура: %s / %s, вход %d px, порог %.2f" % (ARCH, ENCODER, IMG_SIZE, THR))

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD  = np.array([0.229, 0.224, 0.225], np.float32)

def predict_prob(img_rgb):
    """Возвращает карту вероятности ржавчины в размере исходного фото."""
    h, w = img_rgb.shape[:2]
    x = cv2.resize(img_rgb, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_LINEAR)
    x = (x.astype(np.float32) / 255 - MEAN) / STD
    x = torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        p = torch.sigmoid(model(x))[0, 0].cpu().numpy()
    return cv2.resize(p, (w, h), interpolation=cv2.INTER_LINEAR)

# %% ============ ИНФЕРЕНС ПО ПАПКЕ TEST ============
files = sorted(glob.glob(os.path.join(TEST_DIR, "*.jpg")) + glob.glob(os.path.join(TEST_DIR, "*.jpeg")))
if not files:
    raise FileNotFoundError("В папке нет фото .jpg: " + TEST_DIR)
print("Найдено тестовых фото:", len(files))

records = []
TPs = FPs = FNs = 0
for i, fp in enumerate(files, 1):
    bgr = imread_u(fp)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    prob = predict_prob(rgb)
    pred = prob > THR
    stem = os.path.splitext(os.path.basename(fp))[0]
    imwrite_u(os.path.join(MASK_DIR, stem + "_pred.png"), (pred * 255).astype(np.uint8))
    ovl = make_overlay(rgb, pred, (255, 0, 0))
    imwrite_u(os.path.join(OVL_DIR, stem + "_overlay.jpg"), cv2.cvtColor(ovl, cv2.COLOR_RGB2BGR))

    rec = {
        "file": os.path.basename(fp), "width": w, "height": h,
        "rust_pred_pct": round(float(pred.mean() * 100), 3),
        "rust_pred_pixels": int(pred.sum()),
        "mean_confidence": round(float(prob[pred].mean()), 3) if pred.any() else None,
        "max_probability": round(float(prob.max()), 3),
        "rust_true_pct": None, "diff_pct": None, "IoU": None, "Dice": None,
    }
    mp = find_mask(fp)
    if mp:
        gt = read_mask(mp, (h, w))
        tp = int((pred & gt).sum()); fpx = int((pred & ~gt).sum()); fnx = int((~pred & gt).sum())
        TPs += tp; FPs += fpx; FNs += fnx
        rec["rust_true_pct"] = round(float(gt.mean() * 100), 3)
        rec["diff_pct"] = round(rec["rust_pred_pct"] - rec["rust_true_pct"], 3)
        den_i = tp + fpx + fnx
        rec["IoU"] = round(tp / den_i, 3) if den_i else 1.0
        den_d = 2 * tp + fpx + fnx
        rec["Dice"] = round(2 * tp / den_d, 3) if den_d else 1.0
    records.append(rec)
    if i % 10 == 0 or i == len(files):
        print("Обработано %d / %d" % (i, len(files)))

df = pd.DataFrame(records)
df.to_csv(os.path.join(OUT_DIR, "results.csv"), index=False, encoding="utf-8-sig")
summary = {"n_images": len(records), "threshold": THR, "model": os.path.basename(model_path),
           "mean_rust_pred_pct": float(df.rust_pred_pct.mean())}
if TPs + FPs + FNs > 0:
    summary["IoU_total"] = TPs / (TPs + FPs + FNs)
    summary["Dice_total"] = 2 * TPs / (2 * TPs + FPs + FNs)
with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
print("Итого:", summary)
print("Результаты сохранены в:", OUT_DIR)

# %% ============ ОКНО ПРОСМОТРА ============
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class Viewer:
    def __init__(self, files, records):
        self.files, self.records, self.idx = files, records, 0
        self.root = tk.Tk()
        self.root.title("Результаты инференса: ржавчина на листьях")
        sw = self.root.winfo_screenwidth()
        self.panel = int(min(PANEL_MAX, (sw - 140) // 3))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        F = ("Segoe UI", 10); FB = ("Segoe UI", 11, "bold")
        style = ttk.Style(); style.configure("TButton", font=F, padding=6)

        self.title = tk.Label(self.root, text="", font=("Segoe UI", 13, "bold"))
        self.title.pack(pady=(8, 4))

        row = tk.Frame(self.root); row.pack(padx=10)
        self.img_labels, self.caps = [], []
        for cap in ("Исходное фото", "Разметка (эталон)", "Предсказание модели"):
            col = tk.Frame(row); col.pack(side="left", padx=6)
            cl = tk.Label(col, text=cap, font=FB); cl.pack()
            lb = tk.Label(col, bg="#dddddd"); lb.pack()
            self.caps.append(cl); self.img_labels.append(lb)

        box = tk.LabelFrame(self.root, text=" Параметры кадра ", font=FB, padx=10, pady=6)
        box.pack(fill="x", padx=16, pady=8)
        self.vals = {}
        names = ["Файл", "Размер, px", "Доля поражения (модель), %", "Доля поражения (эталон), %",
                 "Разница модель-эталон, %", "Пикселей поражения", "Средняя уверенность модели",
                 "Макс. вероятность", "IoU", "Dice"]
        for k, n in enumerate(names):
            r, c = divmod(k, 2)
            tk.Label(box, text=n + ":", font=F, anchor="w").grid(row=r, column=c * 2, sticky="w", padx=(0, 6), pady=1)
            v = tk.Label(box, text="", font=("Segoe UI", 10, "bold"), anchor="w", width=34)
            v.grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 24))
            self.vals[n] = v
        tk.Label(box, text="Модель: %s / %s, вход %d px, порог %.2f" % (ARCH, ENCODER, IMG_SIZE, THR),
                 font=F, fg="#555555").grid(row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))

        nav = tk.Frame(self.root); nav.pack(pady=(0, 10))
        ttk.Button(nav, text="< Назад", command=self.prev).pack(side="left", padx=4)
        self.scale = tk.Scale(nav, from_=1, to=len(files), orient="horizontal", length=320,
                              command=self.on_scale, font=F)
        self.scale.pack(side="left", padx=8)
        ttk.Button(nav, text="Вперёд >", command=self.next).pack(side="left", padx=4)
        ttk.Button(nav, text="Закрыть", command=self.close).pack(side="left", padx=(30, 4))
        tk.Label(self.root, text="Клавиши: стрелки влево/вправо - листать, Esc - закрыть",
                 font=("Segoe UI", 9), fg="#777777").pack(pady=(0, 6))

        self.root.bind("<Left>", lambda e: self.prev())
        self.root.bind("<Right>", lambda e: self.next())
        self.root.bind("<Escape>", lambda e: self.close())
        self.photos = [None, None, None]
        self.show(0)

    def fit(self, arr):
        h, w = arr.shape[:2]
        s = self.panel / max(h, w)
        arr = cv2.resize(arr, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
        return ImageTk.PhotoImage(Image.fromarray(arr))

    def fmt(self, v, nd=3, suffix=""):
        return "-" if v is None or (isinstance(v, float) and np.isnan(v)) else ("%s%s" % (round(v, nd) if isinstance(v, float) else v, suffix))

    def show(self, i):
        self.idx = max(0, min(len(self.files) - 1, i))
        fp, rec = self.files[self.idx], self.records[self.idx]
        rgb = cv2.cvtColor(imread_u(fp), cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        stem = os.path.splitext(os.path.basename(fp))[0]
        pred = imread_u(os.path.join(MASK_DIR, stem + "_pred.png"), cv2.IMREAD_UNCHANGED) > 0
        mp = find_mask(fp)
        if mp:
            gt_img = make_overlay(rgb, read_mask(mp, (h, w)), (0, 200, 0))
            self.caps[1].config(text="Разметка (эталон)")
        else:
            gt_img = np.full_like(rgb, 221)
            self.caps[1].config(text="Разметка отсутствует")
        imgs = [rgb, gt_img, make_overlay(rgb, pred, (255, 0, 0))]
        for k, a in enumerate(imgs):
            self.photos[k] = self.fit(a)
            self.img_labels[k].config(image=self.photos[k])
        self.title.config(text="Кадр %d из %d" % (self.idx + 1, len(self.files)))
        V = self.vals
        V["Файл"].config(text=rec["file"] if len(rec["file"]) < 34 else rec["file"][:15] + "..." + rec["file"][-16:])
        V["Размер, px"].config(text="%d x %d" % (rec["width"], rec["height"]))
        V["Доля поражения (модель), %"].config(text=self.fmt(rec["rust_pred_pct"]))
        V["Доля поражения (эталон), %"].config(text=self.fmt(rec["rust_true_pct"]) if rec["rust_true_pct"] is not None else "нет разметки")
        V["Разница модель-эталон, %"].config(text=self.fmt(rec["diff_pct"]))
        V["Пикселей поражения"].config(text=str(rec["rust_pred_pixels"]))
        V["Средняя уверенность модели"].config(text=self.fmt(rec["mean_confidence"]))
        V["Макс. вероятность"].config(text=self.fmt(rec["max_probability"]))
        V["IoU"].config(text=self.fmt(rec["IoU"]))
        V["Dice"].config(text=self.fmt(rec["Dice"]))
        self.scale.set(self.idx + 1)

    def on_scale(self, val):
        j = int(float(val)) - 1
        if j != self.idx:
            self.show(j)

    def prev(self): self.show(self.idx - 1)
    def next(self): self.show(self.idx + 1)

    def close(self):
        self.root.quit()
        self.root.destroy()

viewer = Viewer(files, records)
viewer.root.mainloop()
print("Окно закрыто.")