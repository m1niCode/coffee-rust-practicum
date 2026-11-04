# -*- coding: utf-8 -*-
"""
Учебное приложение: обучение сегментации ржавчины на листьях (U-Net) с графическим интерфейсом.
Запуск: F5 в Spyder или  python train_gui.py
Все результаты сохраняются в папку OUT/<имя эксперимента> (рядом со скриптом).
Файл best_model.pth совместим со скриптом инференса (infer_rust.py).
"""
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"            # обход конфликта OpenMP в Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import sys, glob, json, random, time, queue, threading, traceback, subprocess
import numpy as np
import cv2
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
print("Загрузка библиотек (может занять до минуты)...")
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import albumentations as A
import segmentation_models_pytorch as smp
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

# ======================================================================
#                      ТЕКСТЫ ПОДСКАЗОК (кнопки "!")
# ======================================================================
HELP = {
"train": ("Папка обучающей выборки (train)",
 "Здесь лежат фото листьев (.jpg) и рядом маски разметки (.png) с тем же именем "
 "(допустим также суффикс _mask).\n\n"
 "Именно на этих снимках сеть учится. Обычно это 70-80% всех данных.\n"
 "Чем больше и разнообразнее снимки (разное освещение, ракурс, стадия болезни), "
 "тем лучше модель."),
"valid": ("Папка проверочной выборки (valid)",
 "Сеть на этих снимках НЕ учится. После каждой эпохи она проверяется на них, "
 "и по результату выбирается лучшая модель.\n\n"
 "Обычно 10-20% данных. Снимки не должны повторяться в train, иначе оценка "
 "будет завышена (утечка данных). Кнопка «Проверить данные» ищет такие повторы."),
"test": ("Папка тестовой выборки (test)",
 "Используется один раз, после обучения, для честной итоговой оценки.\n\n"
 "Можно оставить поле пустым: тогда тестирование пропускается. "
 "Маски в этой папке необязательны: без них вы получите только долю поражения "
 "по каждому фото, а с масками ещё и IoU и Dice."),
"out": ("Папка результатов",
 "Сюда сохранятся лучшая модель, графики, таблицы метрик и примеры предсказаний. "
 "По умолчанию это папка OUT рядом со скриптом."),
"run": ("Имя эксперимента",
 "Результаты каждого запуска лежат в отдельной подпапке с этим именем. "
 "Давайте имена по смыслу, например «lr0001_epochs30», чтобы потом сравнивать запуски. "
 "Если такое имя уже занято, к нему автоматически добавится номер, и старые результаты не потеряются."),
"preset": ("Готовые наборы параметров",
 "Быстро: маленькое изображение и мало эпох. Подходит, чтобы проверить, что всё работает "
 "(несколько минут на процессоре).\n"
 "Сбалансированно: разумный компромисс скорости и качества.\n"
 "Точно: больше эпох и крупнее изображение, нужен мощный компьютер или видеокарта.\n\n"
 "После выбора набора любой параметр можно изменить вручную."),
"arch": ("Архитектура сети",
 "Устройство нейросети.\n\n"
 "Unet: универсальный вариант, хорошо работает на небольших наборах и даёт чёткие границы. "
 "Рекомендуется для начала.\n"
 "FPN: обычно быстрее, границы могут быть грубее.\n"
 "DeepLabV3Plus: хорош для крупных объектов, обычно тяжелее и медленнее."),
"encoder": ("Энкодер (основа сети)",
 "Часть сети, которая извлекает признаки из фото.\n\n"
 "resnet18: самый лёгкий и быстрый, хватает для учебных задач.\n"
 "resnet34: компромисс.\n"
 "resnet50: самый мощный, но требует больше памяти и времени, а на малых данных "
 "не всегда даёт выигрыш."),
"pretrained": ("Предобученные веса (ImageNet)",
 "Галочка включена: сеть стартует с весов, обученных на миллионах обычных фото. "
 "Она уже «умеет видеть» границы и текстуры, поэтому учится быстрее и точнее.\n\n"
 "Для первого запуска нужен интернет (веса скачиваются один раз). "
 "Для эксперимента снимите галочку и сравните результаты: так студенты увидят пользу предобучения."),
"size": ("Размер изображения, пикселей",
 "Все фото сжимаются до квадрата N на N. Значение должно быть кратно 32.\n\n"
 "256: быстро, но мелкие пятна могут теряться.\n"
 "512: хороший баланс.\n"
 "640 и больше: детальнее, но заметно медленнее и нужно много памяти видеокарты."),
"epochs": ("Число эпох",
 "Эпоха: один полный проход сети по всем обучающим снимкам.\n\n"
 "Слишком мало: сеть не успевает научиться (низкие IoU и Dice).\n"
 "Слишком много: переобучение, потери на train падают, а на valid начинают расти.\n"
 "Для начала 15-30; ориентируйтесь на график: если качество ещё растёт, добавьте эпох."),
"batch": ("Размер пакета (batch)",
 "Сколько снимков сеть обрабатывает за один шаг.\n\n"
 "Больше: стабильнее обучение и быстрее проход, но нужно больше памяти.\n"
 "Меньше: экономит память.\n"
 "Если появилась ошибка нехватки памяти (out of memory), уменьшите значение или размер изображения. "
 "Типично 2-8."),
"lr": ("Скорость обучения (learning rate)",
 "Размер шага, которым сеть исправляет свои ошибки.\n\n"
 "Слишком большая (например 0.01): качество скачет, обучение нестабильно.\n"
 "Слишком маленькая (0.00001): учится очень медленно.\n"
 "Стандарт для этой задачи 0.001. Разумный диапазон 0.0001-0.003. "
 "Можно вписать своё число через точку, например 0.0005."),
"aug": ("Аугментации (искусственное разнообразие данных)",
 "Во время обучения снимки случайно слегка изменяются, и сеть реже запоминает конкретные кадры. "
 "Это особенно полезно, когда снимков мало.\n\n"
 "Отражения: зеркальные копии по горизонтали и вертикали.\n"
 "Повороты на 90°: лист может лежать под любым углом.\n"
 "Яркость и контраст: имитация разного освещения.\n\n"
 "Для эксперимента отключите все галочки и сравните разрыв между качеством на train и valid."),
"dice": ("Доля Dice в функции потерь",
 "Потери складываются из двух частей: BCE (ошибка по каждому пикселю) и Dice (совпадение области).\n\n"
 "Поражённых пикселей обычно намного меньше, чем фона. Тогда одна BCE может «научить» сеть почти "
 "ничего не находить. Dice этому мешает.\n"
 "0: только BCE. 1: только Dice. 0.5: рекомендуемое значение."),
"thr": ("Порог вероятности",
 "Сеть выдаёт для каждого пикселя вероятность ржавчины. Если она выше порога, пиксель считается поражённым.\n\n"
 "Ниже порог: модель находит больше, но растёт число ложных срабатываний.\n"
 "Выше порог: модель осторожнее и может пропускать слабые пятна.\n"
 "Стандартное значение 0.5. Порог сохраняется вместе с моделью."),
"patience": ("Ранняя остановка",
 "Если качество на проверочной выборке (IoU) не улучшается столько эпох подряд, обучение "
 "останавливается досрочно, а лучшая модель остаётся сохранённой.\n\n"
 "0: отключено, пройдут все эпохи. Разумное значение 5-10."),
"seed": ("Случайное зерно (seed)",
 "Число, управляющее случайностью (порядок снимков, аугментации). "
 "При одном и том же seed и параметрах результаты почти повторяются, "
 "что важно для сравнения экспериментов. Измените seed, чтобы оценить разброс результатов."),
"device": ("Устройство вычислений",
 "Авто: использовать видеокарту NVIDIA, если она есть, иначе процессор.\n"
 "Только процессор: медленнее, но работает везде. Выберите, если возникают ошибки видеокарты."),
}

PRESETS = {
    "Быстро (проверка)":      dict(arch="Unet", enc="resnet18", pre=True, size=256, epochs=8,  batch=8, lr="0.001", patience=0),
    "Сбалансированно":        dict(arch="Unet", enc="resnet18", pre=True, size=384, epochs=25, batch=4, lr="0.001", patience=8),
    "Точно (долго)":          dict(arch="Unet", enc="resnet34", pre=True, size=512, epochs=50, batch=4, lr="0.0005", patience=10),
}

# ======================================================================
#                           ФУНКЦИИ ДАННЫХ
# ======================================================================
def imread_u(path, flags=cv2.IMREAD_COLOR):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), flags)

def imwrite_u(path, img):
    ok, buf = cv2.imencode(os.path.splitext(path)[1], img)
    if ok:
        buf.tofile(path)

def find_pairs(folder, need_mask=True):
    pairs = []
    files = []
    for ext in ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG"):
        files += glob.glob(os.path.join(folder, ext))
    for img in sorted(set(files)):
        stem = os.path.splitext(img)[0]
        mask = None
        for cand in (stem + ".png", stem + "_mask.png"):
            if os.path.exists(cand):
                mask = cand
                break
        if mask or not need_mask:
            pairs.append((img, mask))
    return pairs

def read_mask(path):
    m = imread_u(path, cv2.IMREAD_UNCHANGED)
    if m.ndim == 3:
        m = m[..., 0]
    return (m > 0).astype(np.float32)

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

# ======================================================================
#                              ИНТЕРФЕЙС
# ======================================================================
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class App:
    F = ("Segoe UI", 10)
    FB = ("Segoe UI", 10, "bold")

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Обучение модели: ржавчина на листьях")
        self.root.geometry("1000x720")
        self.root.minsize(900, 640)
        self.root.option_add("*Font", self.F)
        st = ttk.Style()
        st.configure("TButton", font=self.F, padding=5)
        st.configure("TNotebook.Tab", font=self.FB, padding=(14, 6))
        self.q = queue.Queue(); self.stop = threading.Event(); self.thread = None
        self.run_dir = None; self.hist = []
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tab1, self.tab2, self.tab3 = ttk.Frame(self.nb), ttk.Frame(self.nb), ttk.Frame(self.nb)
        self.nb.add(self.tab1, text=" 1. Данные ")
        self.nb.add(self.tab2, text=" 2. Параметры обучения ")
        self.nb.add(self.tab3, text=" 3. Обучение и результат ")
        self.build_tab1(); self.build_tab2(); self.build_tab3()
        self.root.after(150, self.poll)
        self.root.after(400, self.draw_plots)

    def help_btn(self, parent, key):
        return tk.Button(parent, text="!", width=2, font=("Segoe UI", 10, "bold"), fg="white", bg="#e08a1e",
                         activebackground="#c9760f", relief="flat", cursor="hand2",
                         command=lambda: self.show_help(key))

    def show_help(self, key):
        title, text = HELP[key]
        w = tk.Toplevel(self.root)
        w.title(title); w.transient(self.root); w.resizable(False, False)
        tk.Label(w, text=title, font=("Segoe UI", 12, "bold"), fg="#8a4b00", wraplength=520, justify="left").pack(
            anchor="w", padx=16, pady=(14, 6))
        tk.Label(w, text=text, font=self.F, wraplength=520, justify="left").pack(anchor="w", padx=16)
        ttk.Button(w, text="Понятно", command=w.destroy).pack(pady=14)
        w.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - w.winfo_height()) // 3
        w.geometry("+%d+%d" % (max(0, x), max(0, y)))
        w.grab_set()

    # ---------------- вкладка 1: данные ----------------
    def build_tab1(self):
        t = self.tab1
        tk.Label(t, text="Выберите папки с данными", font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(14, 2))
        tk.Label(t, text="В каждой папке: фото .jpg и рядом маски .png с тем же именем. Нажмите «!», чтобы узнать подробнее.",
                 fg="#555555").grid(row=1, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 10))
        self.v_train = tk.StringVar(value=os.path.join(BASE_DIR, "train"))
        self.v_valid = tk.StringVar(value=os.path.join(BASE_DIR, "valid"))
        self.v_test = tk.StringVar(value=os.path.join(BASE_DIR, "test"))
        self.v_out = tk.StringVar(value=os.path.join(BASE_DIR, "OUT"))
        self.v_run = tk.StringVar(value="exp1")
        rows = [("Обучающая выборка (train):", self.v_train, "train", True),
                ("Проверочная выборка (valid):", self.v_valid, "valid", True),
                ("Тестовая выборка (test):", self.v_test, "test", True),
                ("Папка для результатов:", self.v_out, "out", True)]
        for i, (lbl, var, key, br) in enumerate(rows):
            r = 2 + i
            tk.Label(t, text=lbl, font=self.FB).grid(row=r, column=0, sticky="w", padx=(14, 8), pady=7)
            ttk.Entry(t, textvariable=var, width=62).grid(row=r, column=1, sticky="we", pady=7)
            ttk.Button(t, text="Обзор...", command=lambda v=var: self.browse(v)).grid(row=r, column=2, padx=6)
            self.help_btn(t, key).grid(row=r, column=3, padx=(0, 14))
        tk.Label(t, text="Имя эксперимента:", font=self.FB).grid(row=6, column=0, sticky="w", padx=(14, 8), pady=7)
        ttk.Entry(t, textvariable=self.v_run, width=30).grid(row=6, column=1, sticky="w", pady=7)
        self.help_btn(t, "run").grid(row=6, column=3, padx=(0, 14))
        t.columnconfigure(1, weight=1)

        ttk.Button(t, text="Проверить данные", command=self.check_data).grid(row=7, column=0, padx=14, pady=(14, 6), sticky="w")
        self.lbl_check = tk.Label(t, text="Нажмите «Проверить данные», чтобы увидеть количество снимков.",
                                  justify="left", anchor="nw", wraplength=900, fg="#333333")
        self.lbl_check.grid(row=8, column=0, columnspan=4, sticky="nw", padx=14)
        ttk.Button(t, text="Далее: параметры >", command=lambda: self.nb.select(1)).grid(
            row=9, column=3, columnspan=1, sticky="e", padx=14, pady=20)

    def browse(self, var):
        d = filedialog.askdirectory(initialdir=var.get() if os.path.isdir(var.get()) else BASE_DIR,
                                    title="Выберите папку")
        if d:
            var.set(os.path.normpath(d))

    def check_data(self):
        self.root.config(cursor="watch"); self.root.update_idletasks()
        try:
            msgs = []
            tr = find_pairs(self.v_train.get()); va = find_pairs(self.v_valid.get())
            te = find_pairs(self.v_test.get(), need_mask=False) if self.v_test.get().strip() else []
            msgs.append("Обучающая выборка: %d снимков с масками" % len(tr))
            msgs.append("Проверочная выборка: %d снимков с масками" % len(va))
            msgs.append("Тестовая выборка: %s" % (("%d снимков (из них с масками: %d)" % (len(te), sum(1 for _, m in te if m)))
                                                  if te else "не задана или пуста (тест будет пропущен)"))
            ok = bool(tr and va)
            if tr:
                sh = np.mean([read_mask(m).mean() for _, m in tr[:100]])
                msgs.append("Доля ржавчины в масках train (по первым 100): %.2f%% пикселей" % (sh * 100))
            if tr and va:
                a = {os.path.basename(p) for p, _ in tr}; b = {os.path.basename(p) for p, _ in va}
                dup = a & b
                if dup:
                    msgs.append("ВНИМАНИЕ: %d файлов с одинаковыми именами есть и в train, и в valid (утечка данных)!" % len(dup))
            if not ok:
                msgs.append("ОШИБКА: в train и valid должны быть пары «фото .jpg + маска .png».")
            self.lbl_check.config(text="\n".join(msgs), fg="#1b6e1b" if ok else "#b00020")
        finally:
            self.root.config(cursor="")

    # ---------------- вкладка 2: параметры ----------------
    def build_tab2(self):
        t = self.tab2
        tk.Label(t, text="Параметры обучения", font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 4))
        self.v_preset = tk.StringVar(value="Сбалансированно")
        tk.Label(t, text="Готовый набор:", font=self.FB).grid(row=1, column=0, sticky="w", padx=14, pady=4)
        cb = ttk.Combobox(t, textvariable=self.v_preset, values=list(PRESETS), state="readonly", width=24)
        cb.grid(row=1, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())
        self.help_btn(t, "preset").grid(row=1, column=2, padx=6)

        self.v_arch = tk.StringVar(); self.v_enc = tk.StringVar(); self.v_pre = tk.BooleanVar()
        self.v_size = tk.StringVar(); self.v_epochs = tk.IntVar(); self.v_batch = tk.IntVar()
        self.v_lr = tk.StringVar(); self.v_flip = tk.BooleanVar(value=True); self.v_rot = tk.BooleanVar(value=True)
        self.v_bright = tk.BooleanVar(value=True); self.v_dice = tk.DoubleVar(value=0.5)
        self.v_thr = tk.DoubleVar(value=0.5); self.v_pat = tk.IntVar(); self.v_seed = tk.IntVar(value=42)
        self.v_dev = tk.StringVar(value="Авто (видеокарта, если есть)")

        def add(row, label, widget_fn, key, hint):
            tk.Label(t, text=label, font=self.FB).grid(row=row, column=0, sticky="w", padx=14, pady=4)
            w = widget_fn(t); w.grid(row=row, column=1, sticky="w", pady=4)
            self.help_btn(t, key).grid(row=row, column=2, padx=6)
            tk.Label(t, text=hint, fg="#666666").grid(row=row, column=3, sticky="w", padx=6)
            return w

        add(2, "Архитектура сети:", lambda p: ttk.Combobox(p, textvariable=self.v_arch, values=["Unet", "FPN", "DeepLabV3Plus"], state="readonly", width=18), "arch", "рекомендуется Unet")
        add(3, "Энкодер:", lambda p: ttk.Combobox(p, textvariable=self.v_enc, values=["resnet18", "resnet34", "resnet50"], state="readonly", width=18), "encoder", "resnet18 - быстро, resnet50 - тяжело")
        add(4, "Предобученные веса:", lambda p: ttk.Checkbutton(p, text="использовать ImageNet", variable=self.v_pre), "pretrained", "нужен интернет при первом запуске")
        add(5, "Размер изображения:", lambda p: ttk.Combobox(p, textvariable=self.v_size, values=["224", "256", "320", "384", "448", "512", "640"], state="readonly", width=18), "size", "кратно 32; 256 быстро, 512 точнее")
        add(6, "Число эпох:", lambda p: ttk.Spinbox(p, from_=1, to=500, textvariable=self.v_epochs, width=10), "epochs", "обычно 15-50")
        add(7, "Размер пакета (batch):", lambda p: ttk.Spinbox(p, from_=1, to=64, textvariable=self.v_batch, width=10), "batch", "2-8; при нехватке памяти уменьшайте")
        add(8, "Скорость обучения:", lambda p: ttk.Combobox(p, textvariable=self.v_lr, values=["0.0001", "0.0003", "0.0005", "0.001", "0.003", "0.01"], width=18), "lr", "стандарт 0.001; можно ввести своё")

        def aug_frame(p):
            f = ttk.Frame(p)
            ttk.Checkbutton(f, text="отражения", variable=self.v_flip).pack(side="left", padx=(0, 8))
            ttk.Checkbutton(f, text="повороты 90°", variable=self.v_rot).pack(side="left", padx=(0, 8))
            ttk.Checkbutton(f, text="яркость/контраст", variable=self.v_bright).pack(side="left")
            return f
        add(9, "Аугментации:", aug_frame, "aug", "больше разнообразия данных")
        add(10, "Доля Dice в потерях:", lambda p: tk.Scale(p, from_=0, to=1, resolution=0.05, orient="horizontal", length=170, variable=self.v_dice), "dice", "рекомендуется 0.5")
        add(11, "Порог вероятности:", lambda p: tk.Scale(p, from_=0.1, to=0.9, resolution=0.05, orient="horizontal", length=170, variable=self.v_thr), "thr", "стандарт 0.5")
        add(12, "Ранняя остановка (эпох):", lambda p: ttk.Spinbox(p, from_=0, to=100, textvariable=self.v_pat, width=10), "patience", "0 - отключена; 5-10 разумно")
        add(13, "Случайное зерно (seed):", lambda p: ttk.Spinbox(p, from_=0, to=99999, textvariable=self.v_seed, width=10), "seed", "для повторяемости результатов")
        add(14, "Устройство:", lambda p: ttk.Combobox(p, textvariable=self.v_dev, values=["Авто (видеокарта, если есть)", "Только процессор"], state="readonly", width=28), "device", "")
        self.apply_preset()
        bf = ttk.Frame(t); bf.grid(row=15, column=0, columnspan=4, sticky="we", padx=14, pady=14)
        ttk.Button(bf, text="< Назад", command=lambda: self.nb.select(0)).pack(side="left")
        ttk.Button(bf, text="Далее: обучение >", command=lambda: self.nb.select(2)).pack(side="right")
        t.columnconfigure(3, weight=1)

    def apply_preset(self):
        p = PRESETS[self.v_preset.get()]
        self.v_arch.set(p["arch"]); self.v_enc.set(p["enc"]); self.v_pre.set(p["pre"])
        self.v_size.set(str(p["size"])); self.v_epochs.set(p["epochs"]); self.v_batch.set(p["batch"])
        self.v_lr.set(p["lr"]); self.v_pat.set(p["patience"])

    # ---------------- вкладка 3: обучение ----------------
    def build_tab3(self):
        t = self.tab3
        top = ttk.Frame(t); top.pack(fill="x", padx=12, pady=(12, 4))
        self.btn_start = ttk.Button(top, text="Начать обучение", command=self.start)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(top, text="Остановить", command=self.on_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        self.btn_open = ttk.Button(top, text="Открыть папку результатов", command=self.open_results, state="disabled")
        self.btn_open.pack(side="left")
        ttk.Button(top, text="Закрыть", command=self.on_close).pack(side="right")
        self.pb = ttk.Progressbar(t, maximum=100)
        self.pb.pack(fill="x", padx=12, pady=4)
        self.lbl_status = tk.Label(t, text="Готов к запуску.", anchor="w", fg="#333333")
        self.lbl_status.pack(fill="x", padx=12)
        pf = ttk.Frame(t); pf.pack(fill="x", padx=12, pady=6)
        self.c1 = tk.Canvas(pf, width=440, height=190, bg="white", highlightthickness=1, highlightbackground="#bbbbbb")
        self.c2 = tk.Canvas(pf, width=440, height=190, bg="white", highlightthickness=1, highlightbackground="#bbbbbb")
        self.c1.pack(side="left", padx=(0, 8), expand=True, fill="x"); self.c2.pack(side="left", expand=True, fill="x")
        self.draw_plots()
        lf = ttk.Frame(t); lf.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.txt = tk.Text(lf, height=10, wrap="word", state="disabled", font=("Consolas", 9), bg="#fafafa")
        sb = ttk.Scrollbar(lf, command=self.txt.yview); self.txt.config(yscrollcommand=sb.set)
        self.txt.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

    def log(self, s):
        self.txt.config(state="normal"); self.txt.insert("end", s + "\n"); self.txt.see("end"); self.txt.config(state="disabled")

    def plot(self, c, title, series):
        c.delete("all")
        w, h = max(int(c.winfo_width()), 300), 190
        c.create_text(w // 2, 12, text=title, font=self.FB)
        l, r, tp, b = 44, w - 12, 28, h - 24
        c.create_rectangle(l, tp, r, b, outline="#999999")
        vals = [v for _, s in series for v in s]
        if not vals:
            c.create_text((l + r) // 2, (tp + b) // 2, text="данные появятся после первой эпохи", fill="#888888"); return
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-9:
            hi = lo + 1e-3
        n = max(len(s) for _, s in series)
        c.create_text(l - 4, tp, text="%.2f" % hi, anchor="e", font=("Segoe UI", 8))
        c.create_text(l - 4, b, text="%.2f" % lo, anchor="e", font=("Segoe UI", 8))
        c.create_text(r, b + 11, text="эпоха %d" % n, anchor="e", font=("Segoe UI", 8))
        cols = ["#1f77b4", "#d62728", "#2ca02c"]
        for k, (name, s) in enumerate(series):
            pts = []
            for i, v in enumerate(s):
                x = l + (r - l) * (i / max(1, n - 1)) if n > 1 else (l + r) / 2
                y = b - (b - tp) * (v - lo) / (hi - lo)
                pts += [x, y]
            if len(pts) >= 4:
                c.create_line(*pts, fill=cols[k], width=2)
            elif len(pts) == 2:
                c.create_oval(pts[0] - 3, pts[1] - 3, pts[0] + 3, pts[1] + 3, fill=cols[k], outline=cols[k])
            c.create_text(l + 8 + k * 110, b + 11, text="— " + name, anchor="w", fill=cols[k], font=("Segoe UI", 8))

    def draw_plots(self):
        h = self.hist
        self.plot(self.c1, "Потери (меньше - лучше)", [("train", [r["train_loss"] for r in h]), ("valid", [r["val_loss"] for r in h])])
        self.plot(self.c2, "Качество на valid (больше - лучше)", [("IoU", [r["val_iou"] for r in h]), ("Dice", [r["val_dice"] for r in h])])

    # ---------------- запуск ----------------
    def collect(self):
        def need(cond, msg):
            if not cond:
                raise ValueError(msg)
        tr, va = self.v_train.get().strip(), self.v_valid.get().strip()
        need(os.path.isdir(tr), "Папка train не найдена. Укажите её на вкладке «Данные».")
        need(os.path.isdir(va), "Папка valid не найдена. Укажите её на вкладке «Данные».")
        te = self.v_test.get().strip()
        if te and not os.path.isdir(te):
            raise ValueError("Папка test не найдена. Укажите её или очистите поле, чтобы пропустить тест.")
        try:
            lr = float(self.v_lr.get().replace(",", "."))
        except ValueError:
            raise ValueError("Скорость обучения должна быть числом, например 0.001.")
        need(0 < lr < 1, "Скорость обучения должна быть между 0 и 1.")
        try:
            epochs, batch, pat, seed = int(self.v_epochs.get()), int(self.v_batch.get()), int(self.v_pat.get()), int(self.v_seed.get())
        except (tk.TclError, ValueError):
            raise ValueError("Эпохи, размер пакета, ранняя остановка и seed должны быть целыми числами.")
        need(epochs >= 1 and batch >= 1 and pat >= 0, "Эпохи и размер пакета должны быть не меньше 1, остановка - не меньше 0.")
        size = int(self.v_size.get())
        need(size % 32 == 0, "Размер изображения должен быть кратен 32.")
        run = self.v_run.get().strip() or "exp1"
        for ch in '<>:"/\\|?*':
            run = run.replace(ch, "_")
        return dict(train_dir=tr, valid_dir=va, test_dir=te, out_dir=self.v_out.get().strip() or os.path.join(BASE_DIR, "OUT"),
                    run_name=run, arch=self.v_arch.get(), encoder=self.v_enc.get(), pretrained=bool(self.v_pre.get()),
                    img_size=size, epochs=epochs, batch=batch, lr=lr,
                    aug=dict(flip=bool(self.v_flip.get()), rot=bool(self.v_rot.get()), bright=bool(self.v_bright.get())),
                    dice_w=float(self.v_dice.get()), thr=float(self.v_thr.get()), patience=pat, seed=seed,
                    device="auto" if self.v_dev.get().startswith("Авто") else "cpu")

    def start(self):
        try:
            cfg = self.collect()
        except ValueError as e:
            messagebox.showerror("Проверьте параметры", str(e)); return
        self.hist = []; self.draw_plots(); self.pb["value"] = 0; self.stop.clear()
        self.txt.config(state="normal"); self.txt.delete("1.0", "end"); self.txt.config(state="disabled")
        self.log("Запуск обучения. Архитектура %s / %s, изображение %d px, эпох %d, batch %d, lr %g."
                 % (cfg["arch"], cfg["encoder"], cfg["img_size"], cfg["epochs"], cfg["batch"], cfg["lr"]))
        self.lbl_status.config(text="Идёт обучение...", fg="#1f5fbf")
        self.btn_start.config(state="disabled"); self.btn_stop.config(state="normal"); self.btn_open.config(state="disabled")
        self.thread = threading.Thread(target=train_worker, args=(cfg, self.q, self.stop), daemon=True)
        self.thread.start()

    def on_stop(self):
        self.stop.set(); self.lbl_status.config(text="Останавливаю после текущего шага...", fg="#b36b00")

    def poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self.log(data)
                elif kind == "progress":
                    self.pb["value"] = data * 100
                elif kind == "epoch":
                    self.hist.append(data); self.draw_plots()
                elif kind == "done":
                    self.run_dir = data; self.finish("Готово.", "#1b6e1b")
                elif kind == "error":
                    self.log("ОШИБКА:\n" + data); self.finish("Ошибка. Подробности в журнале.", "#b00020")
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def finish(self, text, color):
        self.lbl_status.config(text=text, fg=color)
        self.btn_start.config(state="normal"); self.btn_stop.config(state="disabled")
        if self.run_dir and os.path.isdir(self.run_dir):
            self.btn_open.config(state="normal")
        if color == "#1b6e1b":
            self.pb["value"] = 100

    def open_results(self):
        if not (self.run_dir and os.path.isdir(self.run_dir)):
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(self.run_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.run_dir])
            else:
                subprocess.Popen(["xdg-open", self.run_dir])
        except Exception as e:
            messagebox.showinfo("Папка результатов", self.run_dir)

    def on_close(self):
        if self.thread and self.thread.is_alive():
            if not messagebox.askyesno("Выход", "Обучение ещё идёт. Остановить и закрыть окно?"):
                return
            self.stop.set()
        self.root.quit(); self.root.destroy()

if __name__ == "__main__":
    app = App()
    app.root.mainloop()
    print("Окно закрыто.")
