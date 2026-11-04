import { create } from 'zustand';
import { api } from '@/shared/api/client';
import type { AppInfo, Experiment } from '@/shared/api/types';

interface State {
  items: Experiment[];
  info: AppInfo | null;
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
}

export const useExperiments = create<State>((set) => ({
  items: [],
  info: null,
  loading: false,
  error: null,
  load: async () => {
    set({ loading: true, error: null });
    try {
      const [items, info] = await Promise.all([api<Experiment[]>('/experiments'), api<AppInfo>('/info')]);
      set({ items, info, loading: false });
    } catch (e) {
      set({ loading: false, error: e instanceof Error ? e.message : 'Не удалось загрузить эксперименты.' });
    }
  },
}));

/** Лучший эксперимент по итоговой оценке (или по проверке, если теста не было). */
export const bestOf = (items: Experiment[]): Experiment | undefined =>
  items.reduce<Experiment | undefined>((a, b) => {
    const s = (e: Experiment) => e.test_iou ?? e.best_val_iou ?? -1;
    return !a || s(b) > s(a) ? b : a;
  }, undefined);
