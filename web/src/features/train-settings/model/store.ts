import { create } from 'zustand';

export type PresetId = 'fast' | 'bal' | 'acc';

export interface Settings {
  train_dir: string;
  valid_dir: string;
  test_dir: string;
  run_name: string;
  preset: PresetId;
  img_size: number;
  epochs: number;
  early: boolean;
  patience: number;
  flip: boolean;
  rot: boolean;
  bright: boolean;
  arch: 'Unet' | 'FPN' | 'DeepLabV3Plus';
  encoder: 'resnet18' | 'resnet34' | 'resnet50';
  pretrained: boolean;
  batch: number;
  lr: number;
  dice_w: number;
  thr: number;
  seed: number;
  device: 'auto' | 'cpu';
}

/** Наборы параметров из train_gui.py. */
export const PRESETS: Record<PresetId, { title: string; hint: string; time: string; patch: Partial<Settings> }> = {
  fast: { title: 'Быстро', hint: 'Проверить, что всё работает', time: '≈ 5 мин',
    patch: { arch: 'Unet', encoder: 'resnet18', pretrained: true, img_size: 256, epochs: 8, batch: 8, lr: 0.001, early: false, patience: 0 } },
  bal: { title: 'Сбалансированно', hint: 'Разумный выбор для большинства случаев', time: '≈ 30 мин',
    patch: { arch: 'Unet', encoder: 'resnet18', pretrained: true, img_size: 384, epochs: 25, batch: 4, lr: 0.001, early: true, patience: 8 } },
  acc: { title: 'Точно', hint: 'Дольше, нужна мощная видеокарта', time: '≈ 2 ч',
    patch: { arch: 'Unet', encoder: 'resnet34', pretrained: true, img_size: 512, epochs: 50, batch: 4, lr: 0.0005, early: true, patience: 10 } },
};

interface State extends Settings {
  set: (patch: Partial<Settings>) => void;
  applyPreset: (id: PresetId) => void;
}

const initial: Settings = {
  train_dir: '', valid_dir: '', test_dir: '', run_name: 'exp', preset: 'bal',
  img_size: 384, epochs: 25, early: true, patience: 8, flip: true, rot: true, bright: true,
  arch: 'Unet', encoder: 'resnet18', pretrained: true, batch: 4, lr: 0.001, dice_w: 0.5, thr: 0.5, seed: 42, device: 'auto',
};

export const useSettings = create<State>((set) => ({
  ...initial,
  set: (patch) => set(patch),
  applyPreset: (id) => set({ preset: id, ...PRESETS[id].patch }),
}));

/** Тело запроса /api/training/start. */
export function toRequest(s: Settings) {
  return {
    train_dir: s.train_dir, valid_dir: s.valid_dir, test_dir: s.test_dir, run_name: s.run_name,
    arch: s.arch, encoder: s.encoder, pretrained: s.pretrained, img_size: s.img_size, epochs: s.epochs,
    batch: s.batch, lr: s.lr, flip: s.flip, rot: s.rot, bright: s.bright, dice_w: s.dice_w, thr: s.thr,
    patience: s.early ? s.patience : 0, seed: s.seed, device: s.device,
  };
}

/** Грубая оценка времени на процессоре, минуты. Заменить реальным замером, когда он появится. */
export const estimateMinutes = (s: Pick<Settings, 'epochs' | 'img_size'>): number =>
  Math.round(s.epochs * Math.pow(s.img_size / 256, 2) * 0.5);
