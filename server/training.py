# -*- coding: utf-8 -*-
"""Менеджеры обучения: по одному на рабочее пространство, с общей очередью на сервере.

Одновременно идёт не больше config.MAX_PARALLEL обучений (по умолчанию одно), остальные ждут в порядке
поступления. У каждого пользователя может быть только одно задание: ожидающее или идущее.
"""
import os
import queue
import threading
import time

from . import config

_sched = threading.Lock()
_waiting = []          # менеджеры в порядке очереди
_running = 0


class TrainingManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._worker_done = threading.Event()
        self.reset()

    def reset(self):
        self.status = "idle"        # idle | queued | running | stopping | done | error
        self.events = []            # весь журнал событий, интерфейс читает его с нужного номера
        self.epochs = []
        self.progress = 0.0
        self.total_epochs = 0
        self.run_id = None
        self.error = None
        self.started_at = None
        self.cfg = None

    def active(self):
        return self.status in ("queued", "running", "stopping")

    def start(self, cfg):
        from core.training import train_worker  # тяжёлый импорт (torch) только при запуске обучения
        with self._lock:
            if self.active():
                raise RuntimeError("Обучение уже идёт или ждёт очереди.")
            self.reset()
            self._stop.clear()
            self._worker_done.clear()
            self.status, self.cfg, self.total_epochs = "queued", cfg, cfg["epochs"]
            self._add("log", "Ждём свободное место в очереди...")
            threading.Thread(target=self._run, args=(train_worker,), daemon=True).start()

    def stop(self):
        if self.active():
            if self.status != "queued":
                self.status = "stopping"
                self._add("log", "Останавливаю после текущего шага...")
            self._stop.set()

    def queue_ahead(self):
        """Сколько заданий впереди (идущих и ожидающих). 0, если очередь дошла до нас."""
        with _sched:
            if self not in _waiting:
                return 0
            return _running + _waiting.index(self)

    def _run(self, train_worker):
        global _running
        with _sched:
            _waiting.append(self)
        while True:
            with _sched:
                if self._stop.is_set():
                    if self in _waiting:
                        _waiting.remove(self)
                    break
                if _running < config.MAX_PARALLEL and _waiting and _waiting[0] is self:
                    _waiting.pop(0)
                    _running += 1
                    break
            time.sleep(0.5)
        if self._stop.is_set():                      # остановили, пока ждали очереди
            with self._lock:
                self.reset()
            return
        try:
            self.status, self.started_at = "running", time.time()
            threading.Thread(target=self._pump_events, daemon=True).start()
            train_worker(self.cfg, self._q, self._stop)
        finally:
            self._worker_done.set()
            with _sched:
                _running -= 1

    def _add(self, kind, data):
        self.events.append({"n": len(self.events), "kind": kind, "data": data})

    def _pump_events(self):
        while True:
            try:
                kind, data = self._q.get(timeout=0.5)
            except queue.Empty:
                if self._worker_done.is_set() and self._q.empty() and self.active():
                    self.status = "error"
                    self.error = "Обучение неожиданно завершилось."
                    self._add("error", self.error)
                if not self.active():
                    return
                continue
            if kind == "progress":
                self.progress = float(data)      # частые события не копим в журнале
                continue
            if kind == "epoch":
                self.epochs.append(data)
            elif kind == "done":
                self.run_id = os.path.basename(str(data))
                data = self.run_id               # пользователю путь на сервере не нужен
                self.status = "done"
            elif kind == "error":
                self.error = data
                self.status = "error"
            self._add(kind, data)
            if kind in ("done", "error"):
                return

    def eta(self):
        if self.status == "running" and self.progress > 0.01 and self.started_at:
            el = time.time() - self.started_at
            return round(el / self.progress * (1 - self.progress))
        return None

    def light(self):
        return {"status": self.status, "progress": self.progress, "eta_seconds": self.eta(),
                "queue_ahead": self.queue_ahead() if self.status == "queued" else 0}

    def snapshot(self):
        return dict(self.light(), total_epochs=self.total_epochs, epochs=self.epochs, run_id=self.run_id,
                    error=self.error, events_count=len(self.events))


_managers = {}
_managers_lock = threading.Lock()


def get_manager(ws):
    with _managers_lock:
        m = _managers.get(ws)
        if m is None:
            m = _managers[ws] = TrainingManager()
        return m
