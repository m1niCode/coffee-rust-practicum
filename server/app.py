# -*- coding: utf-8 -*-
"""Веб-сервер: API для интерфейса и раздача собранной папки web/dist.

Клиент-серверный режим: данные загружаются на сервер, обучение идёт в общей очереди,
результаты скачиваются. Работает как в корне сайта, так и под префиксом (RUST_BASE_PATH).
"""
import asyncio
import base64
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from core.experiments import list_experiments, load_experiment, model_file
from . import config, security, uploads
from .security import KINDS, current_ws, data_dir, out_dir, require_auth
from .training import get_manager

SHARED = "shared:"
MAX_PHOTOS_PER_CHECK = 50
MAX_PHOTO_BYTES = 40 * 1024 * 1024

class StripPrefix:
    """Срезает префикс (RUST_BASE_PATH) из адреса, если прокси передал его как есть.
    Если прокси префикс уже отрезал, адрес не меняется. Так работают обе схемы настройки."""

    def __init__(self, inner, prefix):
        self.inner, self.prefix = inner, prefix

    async def __call__(self, scope, receive, send):
        p = self.prefix
        if p and scope["type"] in ("http", "websocket"):
            path = scope["path"]
            if path == p or path.startswith(p + "/"):
                scope = dict(scope, path=path[len(p):] or "/",
                             raw_path=(scope.get("raw_path") or path.encode())[len(p):] or b"/")
        await self.inner(scope, receive, send)


app = FastAPI(title="Ржавчина на листьях", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(StripPrefix, prefix=config.BASE_PATH)
api = APIRouter(prefix="/api")
protected = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


# ---------------------------------------------------------------- вход
class Login(BaseModel):
    token: str = ""


@api.get("/auth")
def auth_state(request: Request, response: Response, ws: str = Depends(current_ws)):
    return {"required": security.auth_required(), "authed": security.is_authed(request)}


@api.post("/login")
def login(body: Login, request: Request, response: Response, ws: str = Depends(current_ws)):
    if not security.auth_required():
        return {"ok": True}
    if not security.token_ok(body.token):
        time.sleep(1)                      # замедляем перебор
        raise HTTPException(401, "Неверный токен доступа.")
    security.set_auth_cookie(request, response)
    return {"ok": True}


@api.post("/logout")
def logout(response: Response):
    security.clear_auth_cookie(response)
    return {"ok": True}


def _gpu():
    """(есть ли видеокарта, её название, память в ГБ). Без torch или без видеокарты: (False, None, None)."""
    try:
        import torch
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            return True, p.name, round(p.total_memory / 2**30, 1)
    except Exception:
        pass
    return False, None, None


@protected.get("/info")
def info():
    has_gpu, gpu_name, gpu_gb = _gpu()
    return {"device": "cuda" if has_gpu else "cpu", "gpu_name": gpu_name, "gpu_memory_gb": gpu_gb, "max_upload_mb": config.MAX_UPLOAD // 2**20, "local_paths": config.ALLOW_LOCAL_PATHS,
            "base_dir": config.BASE_DIR if config.ALLOW_LOCAL_PATHS else None}


# ---------------------------------------------------------------- данные
@protected.post("/data/upload")
async def data_upload(request: Request, kind: str = Form(...), files: List[UploadFile] = File(...),
                      ws: str = Depends(current_ws)):
    """Загрузка фото и масок (.jpg, .png) или zip-архива. kind: train, valid, test или auto."""
    length = int(request.headers.get("content-length") or 0)
    if length > config.MAX_UPLOAD + 1024 * 1024:
        raise HTTPException(413, "Слишком большая загрузка (больше %d МБ). Разбейте её на части." % (config.MAX_UPLOAD // 2**20))
    items = [(f.filename or "", f.file) for f in files]
    return await run_in_threadpool(uploads.save_uploads, ws, kind, items)


class Folders(BaseModel):
    train: str = ""
    valid: str = ""
    test: str = ""


@protected.post("/data/check")
def data_check(f: Optional[Folders] = None, ws: str = Depends(current_ws)):
    from core.data import check_folders  # cv2 нужен только здесь
    if config.ALLOW_LOCAL_PATHS and f and (f.train.strip() or f.valid.strip()):
        return check_folders(f.train.strip(), f.valid.strip(), f.test.strip())
    return check_folders(*(data_dir(ws, k) for k in KINDS))


@protected.post("/browse-folder")
def browse_folder():
    """Локальный режим: диалог выбора папки открывается на этом же компьютере отдельным процессом."""
    if not config.ALLOW_LOCAL_PATHS:
        raise HTTPException(403, "Выбор папки на сервере отключён. Загрузите файлы кнопкой.")
    code = ("import tkinter as tk\nfrom tkinter import filedialog\nr=tk.Tk();r.withdraw();r.attributes('-topmost',True)\n"
            "print(filedialog.askdirectory(title='Выберите папку') or '', end='')")
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"path": ""}
    if out.returncode != 0:
        raise HTTPException(500, "Не удалось открыть окно выбора папки. Впишите путь вручную.")
    return {"path": out.stdout.strip()}


class ClearRequest(BaseModel):
    kind: Literal["train", "valid", "test"]


@protected.post("/data/clear")
def data_clear(body: ClearRequest, ws: str = Depends(current_ws)):
    if get_manager(ws).active():
        raise HTTPException(409, "Идёт обучение. Дождитесь его конца или остановите.")
    uploads.clear_kind(ws, body.kind)
    return {"ok": True}


# ---------------------------------------------------------------- эксперименты
def _safe(name):
    return bool(name) and os.path.basename(name) == name and name not in (".", "..") and "\\" not in name


def _resolve(ws, ident):
    """Папка эксперимента по его id. Свои лежат в рабочем пространстве, готовые общие имеют префикс shared:."""
    if ident.startswith(SHARED):
        base, name = config.SHARED_OUT_DIR, ident[len(SHARED):]
    else:
        base, name = out_dir(ws), ident
    if not _safe(name):
        return None, None
    path = os.path.join(base, name)
    return (base, name) if os.path.isdir(path) else (None, None)


@protected.get("/experiments")
def experiments(ws: str = Depends(current_ws)):
    own = [dict(e, shared=False) for e in list_experiments(out_dir(ws))]
    shared = [] if config.ALLOW_LOCAL_PATHS else [dict(e, id=SHARED + e["id"], shared=True)
                                                  for e in list_experiments(config.SHARED_OUT_DIR)]
    return sorted(own + shared, key=lambda e: e["modified"], reverse=True)


def _run_path(ws, ident):
    base, name = _resolve(ws, ident)
    if not base:
        raise HTTPException(404, "Эксперимент не найден.")
    return os.path.join(base, name), name


@protected.get("/experiments/{ident}/download")
def experiment_download(ident: str, ws: str = Depends(current_ws)):
    """Все результаты эксперимента одним zip: модель, метрики, графики."""
    path, name = _run_path(ws, ident)
    tmp = tempfile.mkdtemp(prefix="rust_zip_")
    archive = shutil.make_archive(os.path.join(tmp, name), "zip", root_dir=os.path.dirname(path), base_dir=name)
    return FileResponse(archive, media_type="application/zip", filename=name + ".zip",
                        background=BackgroundTask(shutil.rmtree, tmp, True))


@protected.get("/experiments/{ident}/model")
def experiment_model(ident: str, ws: str = Depends(current_ws)):
    path, name = _run_path(ws, ident)
    mf = model_file(path)
    if not mf:
        raise HTTPException(404, "У эксперимента нет файла модели (.pth).")
    return FileResponse(mf, media_type="application/octet-stream", filename=name + ".pth")


@protected.delete("/experiments/{ident}")
def experiment_delete(ident: str, ws: str = Depends(current_ws)):
    if ident.startswith(SHARED):
        raise HTTPException(403, "Готовые общие модели удалять нельзя.")
    path, _name = _run_path(ws, ident)
    shutil.rmtree(path, ignore_errors=True)
    return {"ok": True}


# ---------------------------------------------------------------- обучение
class TrainRequest(BaseModel):
    train_dir: str = ""      # только в локальном режиме (RUST_ALLOW_LOCAL_PATHS=1)
    valid_dir: str = ""
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


@protected.post("/training/start")
def training_start(r: TrainRequest, ws: str = Depends(current_ws)):
    from core.data import find_pairs
    if r.img_size % 32:
        raise HTTPException(422, "Размер изображения должен быть кратен 32.")
    train_dir, valid_dir, test_dir = (data_dir(ws, k) for k in KINDS)
    if config.ALLOW_LOCAL_PATHS and (r.train_dir.strip() or r.valid_dir.strip()):
        train_dir, valid_dir, test_dir = r.train_dir.strip(), r.valid_dir.strip(), r.test_dir.strip()
        if r.test_dir.strip() and not os.path.isdir(test_dir):
            raise HTTPException(422, "Папка test не найдена. Укажите её или очистите поле.")
    for label, d in (("для обучения", train_dir), ("для проверки", valid_dir)):
        if not os.path.isdir(d) or not find_pairs(d):
            raise HTTPException(422, "Нет загруженных пар «фото + маска» %s. Загрузите их на шаге «Данные»." % label)
    if config.REQUIRE_GPU and r.device == "auto" and not _gpu()[0]:
        raise HTTPException(503, "На сервере недоступна видеокарта, обучение не запущено. Сообщите администратору.")
    run = r.run_name.strip() or "exp"
    for ch in '<>:"/\\|?*.':
        run = run.replace(ch, "_")
    out = out_dir(ws)
    os.makedirs(out, exist_ok=True)
    has_test = os.path.isdir(test_dir) and bool(find_pairs(test_dir, need_mask=False))
    cfg = dict(train_dir=train_dir, valid_dir=valid_dir, test_dir=test_dir if has_test else "", out_dir=out,
               run_name=run, arch=r.arch, encoder=r.encoder, pretrained=r.pretrained, img_size=r.img_size,
               epochs=r.epochs, batch=r.batch, lr=r.lr, aug=dict(flip=r.flip, rot=r.rot, bright=r.bright),
               dice_w=r.dice_w, thr=r.thr, patience=r.patience, seed=r.seed, device=r.device)
    manager = get_manager(ws)
    try:
        manager.start(cfg)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except ImportError as e:
        raise HTTPException(500, "Не установлены библиотеки для обучения (%s). См. README." % e)
    return manager.snapshot()


@protected.post("/training/stop")
def training_stop(ws: str = Depends(current_ws)):
    manager = get_manager(ws)
    manager.stop()
    return manager.snapshot()


@protected.get("/training/state")
def training_state(ws: str = Depends(current_ws)):
    return get_manager(ws).snapshot()


@protected.get("/training/events")
async def training_events(after: int = -1, ws: str = Depends(current_ws)):
    """Поток событий (SSE). after - номер последнего уже полученного события."""
    manager = get_manager(ws)

    async def gen():
        last = after
        while True:
            while last + 1 < len(manager.events):
                last += 1
                yield "data: %s\n\n" % json.dumps(manager.events[last], ensure_ascii=False)
            yield "event: state\ndata: %s\n\n" % json.dumps(manager.light())
            if manager.status in ("done", "error", "idle") and last + 1 >= len(manager.events):
                return
            await asyncio.sleep(0.7)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- применение модели
_models = {}
_sessions = {}     # id проверки -> (рабочее пространство, строки)
_infer_lock = asyncio.Lock()


def _data_url(rgb, max_side=900):
    import cv2
    h, w = rgb.shape[:2]
    k = min(1.0, max_side / max(h, w))
    if k < 1:
        rgb = cv2.resize(rgb, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def _analyze_all(path, threshold, blobs):
    import cv2
    import numpy as np
    from core.inference import RustModel, analyze

    key = (path, threshold)
    if key not in _models:
        _models.clear()
        _models[key] = RustModel(path, threshold)
    model = _models[key]
    results = []
    for filename, data in blobs:
        bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            raise HTTPException(422, "Файл %s не удалось прочитать как фото." % filename)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rec, _pred, overlay = analyze(model, rgb)
        results.append(dict(rec, file=filename, photo=_data_url(rgb), overlay=_data_url(overlay)))
    return model.threshold, results


@protected.post("/inference/analyze")
async def analyze_photos(experiment: str = Form(...), threshold: Optional[float] = Form(None),
                         files: List[UploadFile] = File(...), ws: str = Depends(current_ws)):
    run_path, _name = _run_path(ws, experiment)
    path = model_file(run_path)
    if not path:
        raise HTTPException(404, "У эксперимента нет файла модели (.pth).")
    if len(files) > MAX_PHOTOS_PER_CHECK:
        raise HTTPException(413, "За один раз можно проверить не больше %d фото." % MAX_PHOTOS_PER_CHECK)
    blobs = []
    for up in files:
        data = await up.read(MAX_PHOTO_BYTES + 1)
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(413, "Файл %s слишком большой." % up.filename)
        blobs.append((up.filename, data))
    async with _infer_lock:                      # модель в кэше одна, обрабатываем по очереди
        thr, results = await run_in_threadpool(_analyze_all, path, threshold, blobs)
    sid = uuid.uuid4().hex
    _sessions[sid] = (ws, results)
    for old in list(_sessions)[:-20]:
        _sessions.pop(old, None)
    return {"session": sid, "threshold": thr, "results": results}


@protected.get("/inference/{sid}/results.csv")
def results_csv(sid: str, ws: str = Depends(current_ws)):
    owner, rows = _sessions.get(sid, (None, None))
    if rows is None or owner != ws:
        raise HTTPException(404, "Результаты устарели. Загрузите фото заново.")
    cols = ["file", "width", "height", "rust_pred_pct", "rust_pred_pixels", "mean_confidence", "max_probability"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([r.get(c) for c in cols])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="results.csv"'})


app.include_router(api)
app.include_router(protected)

# ---------------------------------------------------------------- интерфейс (сборка web/dist)
if os.path.isdir(os.path.join(config.DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(config.DIST_DIR, "assets")), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    index = os.path.join(config.DIST_DIR, "index.html")
    if path.startswith("api/"):
        raise HTTPException(404)
    if not os.path.exists(index):
        return JSONResponse({"detail": "Интерфейс не собран. Выполните: cd web && npm install && npm run build"}, 503)
    candidate = os.path.normpath(os.path.join(config.DIST_DIR, path))
    if path and candidate.startswith(config.DIST_DIR) and os.path.isfile(candidate):
        return FileResponse(candidate)
    return FileResponse(index)
