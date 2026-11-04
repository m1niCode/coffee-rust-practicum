# -*- coding: utf-8 -*-
"""Менеджер обучения: запускает core.training в потоке и копит события для интерфейса."""
import queue
import threading
import time


class TrainingManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._thread = None
        self.reset()

    def reset(self):
        self.status = "idle"        # idle | running | stopping | done | error
        self.events = []            # весь журнал событий, интерфейс читает его с нужного номера
        self.epochs = []
        self.progress = 0.0
        self.total_epochs = 0
        self.run_dir = None
        self.error = None
        self.started_at = None
        self.cfg = None

    def running(self):
        return self.status in ("running", "stopping")

    def start(self, cfg):
        from core.training import train_worker  # тяжёлый импорт (torch) только при запуске обучения
        with self._lock:
            if self.running():
                raise RuntimeError("Обучение уже идёт.")
            self.reset()
            self._stop.clear()
            self.status, self.cfg = "running", cfg
            self.total_epochs, self.started_at = cfg["epochs"], time.time()
            self._thread = threading.Thread(target=train_worker, args=(cfg, self._q, self._stop), daemon=True)
            self._pump = threading.Thread(target=self._pump_events, daemon=True)
            self._thread.start()
            self._pump.start()

    def stop(self):
        if self.running():
            self.status = "stopping"
            self._stop.set()
            self._add("log", "Останавливаю после текущего шага...")

    def _add(self, kind, data):
        self.events.append({"n": len(self.events), "kind": kind, "data": data})

    def _pump_events(self):
        while True:
            try:
                kind, data = self._q.get(timeout=0.5)
            except queue.Empty:
                if not self._thread.is_alive() and self.running():
                    self.status = "error"; self.error = "Обучение неожиданно завершилось."
                    self._add("error", self.error)
                if not self.running():
                    return
                continue
            if kind == "progress":
                self.progress = float(data)      # частые события не копим в журнале
                continue
            if kind == "epoch":
                self.epochs.append(data)
            elif kind == "done":
                self.run_dir = data
                self.status = "done"
            elif kind == "error":
                self.error = data
                self.status = "error"
            self._add(kind, data)
            if kind in ("done", "error"):
                return

    def snapshot(self):
        eta = None
        if self.running() and self.progress > 0.01 and self.started_at:
            el = time.time() - self.started_at
            eta = round(el / self.progress * (1 - self.progress))
        return {
            "status": self.status, "progress": self.progress, "total_epochs": self.total_epochs,
            "epochs": self.epochs, "run_dir": self.run_dir, "error": self.error, "eta_seconds": eta,
            "events_count": len(self.events),
            "config": self.cfg,
        }


manager = TrainingManager()
