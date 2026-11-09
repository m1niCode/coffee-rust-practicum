# -*- coding: utf-8 -*-
"""Запуск приложения: python app.py

Локально: окно откроется в браузере. На сервере: HOST=0.0.0.0 RUST_TOKEN=... python app.py --no-browser
Настройки (токен, префикс, папки) описаны в server/config.py.
"""
import os
import sys
import threading
import time
import webbrowser

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")        # обход конфликта OpenMP в Windows
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from server import config  # noqa: E402


def main():
    import uvicorn
    shown = "127.0.0.1" if config.HOST in ("0.0.0.0", "::") else config.HOST
    url = "http://%s:%d%s/" % (shown, config.PORT, config.BASE_PATH)
    if "--no-browser" not in sys.argv:
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
    if config.ALLOW_LOCAL_PATHS and config.HOST not in ("127.0.0.1", "localhost", "::1"):
        print("ВНИМАНИЕ: включён RUST_ALLOW_LOCAL_PATHS, а сервер доступен по сети: пользователи смогут читать любые папки на этом компьютере.")
    if config.HOST not in ("127.0.0.1", "localhost", "::1") and not config.TOKEN:
        print("ВНИМАНИЕ: сервер доступен по сети, а RUST_TOKEN не задан. Любой, кто знает адрес, сможет им пользоваться.")
    print("Приложение запущено: %s  (остановить: Ctrl+C)" % url)
    uvicorn.run("server.app:app", host=config.HOST, port=config.PORT, log_level="warning",
                proxy_headers=True, forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"))


if __name__ == "__main__":
    main()
