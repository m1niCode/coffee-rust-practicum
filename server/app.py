# -*- coding: utf-8 -*-
"""Веб-сервер приложения: API для интерфейса и раздача собранной папки web/dist."""
import asyncio
import base64
import csv
import io
import json
import os
import subprocess
import sys
import uuid
from typing import List, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.experiments import list_experiments, load_experiment, model_file
from .training import manager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.environ.get("RUST_OUT_DIR", os.path.join(BASE_DIR, "OUT"))
DIST_DIR = os.path.join(BASE_DIR, "web", "dist")

app = FastAPI(title="Ржавчина на листьях")


# ---------------------------------------------------------------- данные
class Folders(BaseModel):
    train: str = ""
    valid: str = ""
    test: str = ""


@app.post("/api/data/check")
def data_check(f: Folders):
    from core.data import check_folders  # cv2 нужен только здесь
    return check_folders(f.train.strip(), f.valid.strip(), f.test.strip())


@app.post("/api/browse-folder")
def browse_folder():
    """Диалог выбора папки на стороне Python. Запускается отдельным процессом, чтобы не мешать серверу."""
    code = ("import tkinter as tk\nfrom tkinter import filedialog\nr=tk.Tk();r.withdraw();r.attributes('-topmost',True)\n"
            "print(filedialog.askdirectory(title='Выберите папку') or '', end='')")
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"path": ""}
    if out.returncode != 0:
        raise HTTPException(500, "Не удалось открыть окно выбора папки. Впишите путь вручную.")
    return {"path": out.stdout.strip()}


@app.get("/api/info")
def info():
    device = "cpu"
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        pass
    return {"out_dir": OUT_DIR, "base_dir": BASE_DIR, "device": device}


# ---------------------------------------------------------------- эксперименты
@app.get("/api/experiments")
def experiments():
    return list_experiments(OUT_DIR)


@app.post("/api/experiments/{name}/open-folder")
def open_experiment_folder(name: str):
    path = os.path.join(OUT_DIR, name)
    if not os.path.isdir(path) or os.path.dirname(os.path.abspath(path)) != os.path.abspath(OUT_DIR):
        raise HTTPException(404, "Папка эксперимента не найдена.")
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
    return {"ok": True}


# ---------------------------------------------------------------- обучение
class TrainRequest(BaseModel):
    train_dir: str
    valid_dir: str
    test_dir: str = ""
    run_name: str = "exp"
    arch: Literal["Unet", "FPN", "DeepLabV3Plus"] = "Unet"
    encoder: Literal["resnet18", "resnet34", "resnet50"] = "resnet18"
    pretrained: bool = True
    img_size: int = Field(384, ge=64, le=1024)
    epochs: int = Field(25, ge=1, le=500)
    batch: int = Field(4, ge=1, le=64)
    lr: float = Field(0.001, gt=0, lt=1)
    flip: bool = True
    rot: bool = True
    bright: bool = True
    dice_w: float = Field(0.5, ge=0, le=1)
    thr: float = Field(0.5, ge=0.1, le=0.9)
    patience: int = Field(0, ge=0, le=100)
    seed: int = 42
    device: Literal["auto", "cpu"] = "auto"


@app.post("/api/training/start")
def training_start(r: TrainRequest):
    if r.img_size % 32:
        raise HTTPException(422, "Размер изображения должен быть кратен 32.")
    if not os.path.isdir(r.train_dir) or not os.path.isdir(r.valid_dir):
        raise HTTPException(422, "Папки train и valid не найдены. Проверьте их на шаге «Данные».")
    if r.test_dir and not os.path.isdir(r.test_dir):
        raise HTTPException(422, "Папка test не найдена. Укажите её или очистите поле.")
    run = r.run_name.strip() or "exp"
    for ch in '<>:"/\\|?*':
        run = run.replace(ch, "_")
    cfg = dict(train_dir=r.train_dir, valid_dir=r.valid_dir, test_dir=r.test_dir, out_dir=OUT_DIR, run_name=run,
               arch=r.arch, encoder=r.encoder, pretrained=r.pretrained, img_size=r.img_size, epochs=r.epochs,
               batch=r.batch, lr=r.lr, aug=dict(flip=r.flip, rot=r.rot, bright=r.bright), dice_w=r.dice_w,
               thr=r.thr, patience=r.patience, seed=r.seed, device=r.device)
    try:
        manager.start(cfg)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except ImportError as e:
        raise HTTPException(500, "Не установлены библиотеки для обучения (%s). См. README." % e)
    return manager.snapshot()


@app.post("/api/training/stop")
def training_stop():
    manager.stop()
    return manager.snapshot()


@app.get("/api/training/state")
def training_state():
    return manager.snapshot()


@app.get("/api/training/events")
async def training_events(after: int = -1):
    """Поток событий (SSE). after - номер последнего уже полученного события."""
    async def gen():
        last = after
        while True:
            while last + 1 < len(manager.events):
                last += 1
                yield "data: %s\n\n" % json.dumps(manager.events[last], ensure_ascii=False)
            yield "event: state\ndata: %s\n\n" % json.dumps({"status": manager.status, "progress": manager.progress,
                                                            "eta_seconds": manager.snapshot()["eta_seconds"]})
            if manager.status in ("done", "error", "idle") and last + 1 >= len(manager.events):
                return
            await asyncio.sleep(0.7)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- применение модели
_models = {}
_sessions = {}


def _data_url(rgb, max_side=900):
    import cv2
    h, w = rgb.shape[:2]
    k = min(1.0, max_side / max(h, w))
    if k < 1:
        rgb = cv2.resize(rgb, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


@app.post("/api/inference/analyze")
async def analyze_photos(experiment: str = Form(...), threshold: Optional[float] = Form(None),
                         files: List[UploadFile] = File(...)):
    import cv2
    import numpy as np
    from core.inference import RustModel, analyze

    run_dir = os.path.join(OUT_DIR, experiment)
    path = model_file(run_dir) if os.path.isdir(run_dir) else None
    if not path:
        raise HTTPException(404, "У эксперимента нет файла модели (.pth).")
    key = (path, threshold)
    if key not in _models:
        _models.clear()
        _models[key] = RustModel(path, threshold)
    model = _models[key]

    results = []
    for up in files:
        data = await up.read()
        bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            raise HTTPException(422, "Файл %s не удалось прочитать как фото." % up.filename)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rec, _pred, overlay = analyze(model, rgb)
        rec = dict(rec, file=up.filename, photo=_data_url(rgb), overlay=_data_url(overlay))
        results.append(rec)
    sid = uuid.uuid4().hex
    _sessions[sid] = results
    for old in list(_sessions)[:-5]:
        _sessions.pop(old, None)
    return {"session": sid, "threshold": model.threshold, "results": results}


@app.get("/api/inference/{sid}/results.csv")
def results_csv(sid: str):
    rows = _sessions.get(sid)
    if rows is None:
        raise HTTPException(404, "Результаты устарели. Загрузите фото заново.")
    cols = ["file", "width", "height", "rust_pred_pct", "rust_pred_pixels", "mean_confidence", "max_probability"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([r.get(c) for c in cols])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="results.csv"'})


# ---------------------------------------------------------------- интерфейс (сборка web/dist)
if os.path.isdir(os.path.join(DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    index = os.path.join(DIST_DIR, "index.html")
    if path.startswith("api/"):
        raise HTTPException(404)
    if not os.path.exists(index):
        return JSONResponse({"detail": "Интерфейс не собран. Выполните: cd web && npm install && npm run build"}, 503)
    candidate = os.path.normpath(os.path.join(DIST_DIR, path))
    if path and candidate.startswith(DIST_DIR) and os.path.isfile(candidate):
        return FileResponse(candidate)
    return FileResponse(index)
