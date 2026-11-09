export interface Experiment {
  id: string;
  arch: string;
  encoder: string;
  image_size: number | null;
  epochs_planned: number | null;
  epochs_done: number;
  batch: number | null;
  lr: number | null;
  threshold: number;
  test_iou: number | null;
  test_dice: number | null;
  test_images: number | null;
  best_val_iou: number | null;
  curves: { val_iou: number[]; train_loss: number[]; val_loss: number[] };
  has_model: boolean;
  modified: number;
  /** Готовая модель, общая для всех. Только для чтения. */
  shared: boolean;
}

export interface FolderInfo {
  exists: boolean;
  photos: number;
  pairs: number;
}

export interface DataCheck {
  train: FolderInfo;
  valid: FolderInfo;
  test: FolderInfo;
  rust_share_train: number | null;
  duplicates: string[];
  duplicates_count: number;
  ok: boolean;
}

export interface EpochRow {
  epoch: number;
  train_loss: number;
  val_loss: number;
  val_iou: number;
  val_dice: number;
}

export type TrainStatus = 'idle' | 'queued' | 'running' | 'stopping' | 'done' | 'error';

export interface TrainSnapshot {
  status: TrainStatus;
  progress: number;
  total_epochs: number;
  epochs: EpochRow[];
  run_id: string | null;
  error: string | null;
  eta_seconds: number | null;
  queue_ahead: number;
}

export interface UploadResult {
  saved: { train: number; valid: number; test: number };
  skipped: number;
}

export interface TrainEvent {
  n: number;
  kind: 'log' | 'epoch' | 'done' | 'error';
  data: unknown;
}

export interface PhotoResult {
  file: string;
  width: number;
  height: number;
  rust_pred_pct: number;
  mean_confidence: number | null;
  rust_true_pct: number | null;
  IoU: number | null;
  Dice: number | null;
  photo: string;
  overlay: string;
}

export interface AnalyzeResponse {
  session: string;
  threshold: number;
  results: PhotoResult[];
}

export interface AppInfo {
  device: 'cpu' | 'cuda';
  gpu_name: string | null;
  gpu_memory_gb: number | null;
  max_upload_mb: number;
  /** Локальный режим для занятий: данные берутся из папок на этом компьютере. */
  local_paths: boolean;
  base_dir: string | null;
}
