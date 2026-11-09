# -*- coding: utf-8 -*-
"""Настройки сервера из переменных окружения.

RUST_TOKEN          общий токен доступа. Не задан: вход без пароля (локальный режим).
RUST_BASE_PATH      префикс, под которым приложение открыто (например /kofi). Работает и если прокси
                    отрезает префикс, и если передаёт его как есть.
RUST_DATA_DIR       рабочие папки пользователей (загруженные данные и их эксперименты).
RUST_OUT_DIR        общие готовые модели: видны всем, только для чтения.
RUST_ALLOW_LOCAL_PATHS=1  локальный режим для занятий: данные берутся из папок на этом компьютере (поля путей и «Обзор…»),
                    результаты пишутся в RUST_OUT_DIR. Для общего сервера не включать: пользователь сможет читать любые папки.
RUST_MAX_UPLOAD_MB  максимум на один запрос загрузки (по умолчанию 1024).
RUST_MAX_WORKSPACE_MB  максимум данных одного пользователя (по умолчанию 4096).
RUST_MAX_PARALLEL   сколько обучений идёт одновременно (по умолчанию 1).
HOST, PORT          адрес, на котором слушает сервер.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def normalize_base_path(value):
    value = (value or "").strip().strip("/")
    return "/" + value if value else ""


ALLOW_LOCAL_PATHS = os.environ.get("RUST_ALLOW_LOCAL_PATHS", "").strip() == "1"
TOKEN = os.environ.get("RUST_TOKEN", "").strip()
BASE_PATH = normalize_base_path(os.environ.get("RUST_BASE_PATH"))
DATA_DIR = os.path.abspath(os.environ.get("RUST_DATA_DIR", os.path.join(BASE_DIR, "data")))
SHARED_OUT_DIR = os.path.abspath(os.environ.get("RUST_OUT_DIR", os.path.join(BASE_DIR, "OUT")))
DIST_DIR = os.path.join(BASE_DIR, "web", "dist")
MAX_UPLOAD = _int("RUST_MAX_UPLOAD_MB", 1024) * 1024 * 1024
MAX_WORKSPACE = _int("RUST_MAX_WORKSPACE_MB", 4096) * 1024 * 1024
MAX_PARALLEL = max(1, _int("RUST_MAX_PARALLEL", 1))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = _int("PORT", 8765)
