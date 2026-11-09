# -*- coding: utf-8 -*-
"""Вход по общему токену и личное рабочее пространство пользователя.

Рабочее пространство определяется случайным идентификатором в cookie. Он длинный и неугадываемый,
поэтому чужие данные не видны. Токен в cookie хранится не в открытом виде.
"""
import hashlib
import hmac
import os
import re
import uuid

from fastapi import HTTPException, Request, Response

from . import config

WS_COOKIE = "rust_ws"
AUTH_COOKIE = "rust_auth"
_WS_RE = re.compile(r"^[0-9a-f]{32}$")


def _session_value():
    return hmac.new(config.TOKEN.encode(), b"rust-session", hashlib.sha256).hexdigest()


def auth_required():
    return bool(config.TOKEN)


def is_authed(request: Request):
    if not config.TOKEN:
        return True
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer ") and hmac.compare_digest(header[7:].strip(), config.TOKEN):
        return True
    return hmac.compare_digest(request.cookies.get(AUTH_COOKIE, ""), _session_value())


def token_ok(token):
    return bool(config.TOKEN) and hmac.compare_digest(token.strip(), config.TOKEN)


def _https(request: Request):
    return request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip() == "https"


def _set_cookie(request: Request, response: Response, key, value, max_age):
    response.set_cookie(key, value, max_age=max_age, httponly=True, samesite="lax",
                        secure=_https(request), path=config.BASE_PATH or "/")


def set_auth_cookie(request: Request, response: Response):
    _set_cookie(request, response, AUTH_COOKIE, _session_value(), 30 * 24 * 3600)


def clear_auth_cookie(response: Response):
    response.delete_cookie(AUTH_COOKIE, path=config.BASE_PATH or "/")


def require_auth(request: Request):
    if not is_authed(request):
        raise HTTPException(401, "Нужен вход. Введите токен доступа.")


def current_ws(request: Request, response: Response):
    """Идентификатор рабочего пространства. Если cookie нет, создаётся новый. Вход проверяет роутер."""
    ws = request.cookies.get(WS_COOKIE, "")
    if not _WS_RE.match(ws):
        ws = uuid.uuid4().hex
        _set_cookie(request, response, WS_COOKIE, ws, 365 * 24 * 3600)
    return ws


# ---------------------------------------------------------------- папки рабочего пространства
KINDS = ("train", "valid", "test")


def ws_root(ws):
    return os.path.join(config.DATA_DIR, "workspaces", ws)


def data_dir(ws, kind):
    if kind not in KINDS:
        raise HTTPException(422, "Неизвестная папка данных.")
    return os.path.join(ws_root(ws), "data", kind)


def out_dir(ws):
    return os.path.join(ws_root(ws), "OUT")


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total
