import { create } from 'zustand';
import { api, apiUrl, post } from '@/shared/api/client';
import type { EpochRow, TrainEvent, TrainSnapshot, TrainStatus } from '@/shared/api/types';

interface State {
  status: TrainStatus;
  progress: number;
  etaSeconds: number | null;
  epochs: EpochRow[];
  log: string[];
  runId: string | null;
  queueAhead: number;
  error: string | null;
  totalEpochs: number;
  start: (cfg: Record<string, unknown>) => Promise<void>;
  stop: () => Promise<void>;
  /** Подключиться к уже идущему обучению (например, после обновления страницы). */
  attach: () => Promise<void>;
}

let source: EventSource | null = null;

export const useTraining = create<State>((set, get) => {
  const listen = () => {
    source?.close();
    const es = new EventSource(apiUrl('/training/events?after=-1'));
    source = es;
    es.onmessage = (m: MessageEvent<string>) => {
      const ev = JSON.parse(m.data) as TrainEvent;
      if (ev.kind === 'log') set((s) => ({ log: [...s.log, String(ev.data)] }));
      else if (ev.kind === 'epoch') set((s) => ({ epochs: [...s.epochs, ev.data as EpochRow] }));
      else if (ev.kind === 'done') set({ runId: String(ev.data) });
      else if (ev.kind === 'error') set({ error: String(ev.data) });
    };
    es.addEventListener('state', (m) => {
      const s = JSON.parse((m as MessageEvent<string>).data) as { status: TrainStatus; progress: number; eta_seconds: number | null; queue_ahead: number };
      set({ status: s.status, progress: s.progress, etaSeconds: s.eta_seconds, queueAhead: s.queue_ahead });
      if (s.status === 'done' || s.status === 'error' || s.status === 'idle') {
        es.close();
        if (source === es) source = null;
      }
    });
  };

  return {
    status: 'idle', progress: 0, etaSeconds: null, epochs: [], log: [], runId: null, queueAhead: 0, error: null, totalEpochs: 0,
    start: async (cfg) => {
      const snap = await post<TrainSnapshot>('/training/start', cfg);
      set({ status: snap.status, progress: 0, etaSeconds: null, epochs: [], log: [], runId: null, queueAhead: snap.queue_ahead, error: null, totalEpochs: snap.total_epochs });
      listen();
    },
    stop: async () => {
      const snap = await post<TrainSnapshot>('/training/stop');
      set({ status: snap.status });
    },
    attach: async () => {
      if (source || get().status !== 'idle') return;
      const snap = await api<TrainSnapshot>('/training/state');
      if (snap.status === 'idle') return;
      set({ status: snap.status, totalEpochs: snap.total_epochs, progress: snap.progress, queueAhead: snap.queue_ahead });
      listen();
    },
  };
});
