export const pct = (v: number | null | undefined): string => (v == null ? '—' : Math.round(v * 100) + '%');

export const pct1 = (v: number | null | undefined): string => (v == null ? '—' : v.toFixed(1).replace('.', ',') + '%');

export type Tone = 'ok' | 'warn';

/** Слова «Отлично / Хорошо / Можно лучше». Пороги 75% и 65% предложены для обсуждения, это не научный стандарт. */
export function verdict(iou: number | null): { text: string; tone: Tone } {
  if (iou == null) return { text: 'Нет оценки', tone: 'warn' };
  if (iou >= 0.75) return { text: 'Отлично', tone: 'ok' };
  if (iou >= 0.65) return { text: 'Хорошо', tone: 'ok' };
  return { text: 'Можно лучше', tone: 'warn' };
}

export function minutes(seconds: number | null): string {
  if (seconds == null) return 'считаем время…';
  const m = Math.max(1, Math.round(seconds / 60));
  return m < 90 ? `примерно ${m} мин` : `примерно ${(m / 60).toFixed(1)} ч`;
}
