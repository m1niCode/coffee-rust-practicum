# -*- coding: utf-8 -*-
"""Запуск приложения: python app.py  (окно откроется в браузере)."""
import os
import sys
import threading
import time
import webbrowser

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")        # обход конфликта OpenMP в Windows
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", "8765"))


def main():
    import uvicorn
    url = "http://%s:%d" % (HOST, PORT)
    if "--no-browser" not in sys.argv:
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
    print("Приложение запущено: %s  (остановить: Ctrl+C)" % url)
    uvicorn.run("server.app:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
