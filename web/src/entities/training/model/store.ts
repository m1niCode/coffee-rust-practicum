import { create } from 'zustand';
import { api, post } from '@/shared/api/client';
import type { EpochRow, TrainEvent, TrainSnapshot, TrainStatus } from '@/shared/api/types';

interface State {
  status: TrainStatus;
  progress: number;
  etaSeconds: number | null;
  epochs: EpochRow[];
  log: string[];
  runDir: string | null;
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
    const es = new EventSource('/api/training/events?after=-1');
    source = es;
    es.onmessage = (m: MessageEvent<string>) => {
      const ev = JSON.parse(m.data) as TrainEvent;
      if (ev.kind === 'log') set((s) => ({ log: [...s.log, String(ev.data)] }));
      else if (ev.kind === 'epoch') set((s) => ({ epochs: [...s.epochs, ev.data as EpochRow] }));
      else if (ev.kind === 'done') set({ runDir: String(ev.data) });
      else if (ev.kind === 'error') set({ error: String(ev.data) });
    };
    es.addEventListener('state', (m) => {
      const s = JSON.parse((m as MessageEvent<string>).data) as { status: TrainStatus; progress: number; eta_seconds: number | null };
      set({ status: s.status, progress: s.progress, etaSeconds: s.eta_seconds });
      if (s.status === 'done' || s.status === 'error' || s.status === 'idle') {
        es.close();
        if (source === es) source = null;
      }
    });
  };

  return {
    status: 'idle', progress: 0, etaSeconds: null, epochs: [], log: [], runDir: null, error: null, totalEpochs: 0,
    start: async (cfg) => {
      const snap = await post<TrainSnapshot>('/training/start', cfg);
      set({ status: snap.status, progress: 0, etaSeconds: null, epochs: [], log: [], runDir: null, error: null, totalEpochs: snap.total_epochs });
      listen();
    },
    stop: async () => {
      await post<TrainSnapshot>('/training/stop');
      set({ status: 'stopping' });
    },
    attach: async () => {
      if (source || get().status !== 'idle') return;
      const snap = await api<TrainSnapshot>('/training/state');
      if (snap.status === 'idle') return;
      set({ status: snap.status, totalEpochs: snap.total_epochs, progress: snap.progress });
      listen();
    },
  };
});
