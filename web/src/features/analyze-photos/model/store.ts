import { create } from 'zustand';
import { api, ApiError } from '@/shared/api/client';
import type { AnalyzeResponse, PhotoResult } from '@/shared/api/types';

interface State {
  experiment: string;
  threshold: number;
  results: PhotoResult[];
  session: string | null;
  busy: boolean;
  error: string | null;
  setExperiment: (id: string) => void;
  setThreshold: (t: number) => void;
  analyze: (files: File[]) => Promise<void>;
}

let lastFiles: File[] = [];

export const useAnalyze = create<State>((set, get) => ({
  experiment: '', threshold: 0.5, results: [], session: null, busy: false, error: null,
  setExperiment: (experiment) => set({ experiment }),
  setThreshold: (threshold) => set({ threshold }),
  analyze: async (files) => {
    const { experiment, threshold } = get();
    const photos = files.length ? files : lastFiles;
    if (!experiment) return set({ error: 'Выберите модель.' });
    if (!photos.length) return;
    lastFiles = photos;
    set({ busy: true, error: null });
    const fd = new FormData();
    fd.append('experiment', experiment);
    fd.append('threshold', String(threshold));
    photos.forEach((f) => fd.append('files', f));
    try {
      const r = await api<AnalyzeResponse>('/inference/analyze', { method: 'POST', body: fd });
      set({ results: r.results, session: r.session, busy: false });
    } catch (e) {
      set({ busy: false, error: e instanceof ApiError ? e.message : 'Не удалось обработать фото.' });
    }
  },
}));
