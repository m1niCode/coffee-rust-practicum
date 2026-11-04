import { useState } from 'react';
import { useTraining } from '@/entities/training/model/store';
import { estimateMinutes, PRESETS, toRequest, useSettings, type PresetId, type Settings } from '@/features/train-settings/model/store';
import { go } from '@/shared/lib/route';
import { HelpButton } from '@/shared/ui/help';
import { ErrorBox, PageHead } from '@/shared/ui/PageHead';
import type { HelpKey } from '@/shared/config/help';

const Field = ({ title, hint, help, children }: { title: string; hint?: string; help: HelpKey; children: React.ReactNode }) => (
  <div className="field">
    <div className="lbl">{title}<HelpButton topic={help} /></div>
    {hint && <div className="hint">{hint}</div>}
    {children}
  </div>
);

export function ParamsPage() {
  const s = useSettings();
  const status = useTraining((t) => t.status);
  const start = useTraining((t) => t.start);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const running = status === 'running' || status === 'stopping';

  const begin = async () => {
    setErr(null);
    if (!s.train_dir.trim() || !s.valid_dir.trim()) {
      setErr('Сначала укажите папки train и valid на шаге «Данные».');
      return;
    }
    setBusy(true);
    try { await start(toRequest(s)); go('train'); }
    catch (e) { setErr(e instanceof Error ? e.message : 'Не удалось начать обучение.'); }
    finally { setBusy(false); }
  };

  const min = estimateMinutes(s);
  const num = (k: keyof Settings) => (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => s.set({ [k]: Number(e.target.value) } as Partial<Settings>);

  return (
    <section>
      <PageHead step="Шаг 2 из 4" title="Как учить модель">
        Для первого раза выберите готовый набор. Любой параметр можно изменить, а сложные спрятаны в «Расширенных настройках».
      </PageHead>
      <div className="seg-preset grid3">
        {(Object.keys(PRESETS) as PresetId[]).map((id) => (
          <label key={id}>
            <input type="radio" name="preset" checked={s.preset === id} onChange={() => s.applyPreset(id)} />
            <div className="preset"><b>{PRESETS[id].title}</b><span className="muted">{PRESETS[id].hint}</span>
              <span className="chip mute" style={{ width: 'max-content' }}>{PRESETS[id].time}</span></div>
          </label>
        ))}
      </div>
      <div className="grid2" style={{ marginTop: 22, gridTemplateColumns: 'minmax(0,1.6fr) minmax(0,1fr)', alignItems: 'start' }}>
        <div className="card">
          <h2>Основные настройки</h2>
          <Field title="Подробность снимков" help="size" hint="Чем крупнее, тем лучше видны мелкие пятна, но тем дольше учится модель.">
            <div className="seg">
              {[[256, 'Низкая'], [384, 'Средняя'], [512, 'Высокая']].map(([v, t]) => (
                <label key={v}><input type="radio" name="size" checked={s.img_size === v} onChange={() => s.set({ img_size: Number(v) })} /><span>{t} · {v}</span></label>
              ))}
            </div>
          </Field>
          <Field title="Сколько раз просмотреть все фото" help="epochs" hint="Это число эпох. Обычно 15–50. Если качество на графике ещё растёт, добавьте.">
            <div className="stepper">
              <button type="button" aria-label="Меньше" onClick={() => s.set({ epochs: Math.max(1, s.epochs - 5) })}>−</button>
              <output>{s.epochs}</output>
              <button type="button" aria-label="Больше" onClick={() => s.set({ epochs: Math.min(500, s.epochs + 5) })}>+</button>
            </div>
          </Field>
          <Field title="Остановиться, если нет улучшения" help="patience" hint="Обучение закончится раньше, а лучшая модель сохранится.">
            <label className="toggle"><input type="checkbox" checked={s.early} onChange={(e) => s.set({ early: e.target.checked, patience: s.patience || 8 })} />
              <span>Остановить через {s.patience || 8} эпох без улучшения</span></label>
          </Field>
          <Field title="Разнообразить фото при обучении" help="aug" hint="Программа слегка отражает, поворачивает и меняет яркость снимков. Так она запоминает меньше лишнего.">
            <div className="seg">
              <label><input type="checkbox" checked={s.flip} onChange={(e) => s.set({ flip: e.target.checked })} /><span>Отражения</span></label>
              <label><input type="checkbox" checked={s.rot} onChange={(e) => s.set({ rot: e.target.checked })} /><span>Повороты</span></label>
              <label><input type="checkbox" checked={s.bright} onChange={(e) => s.set({ bright: e.target.checked })} /><span>Яркость и контраст</span></label>
            </div>
          </Field>
          <details className="adv">
            <summary>Расширенные настройки
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 9l6 6 6-6" /></svg>
            </summary>
            <Field title="Тип нейросети" help="arch">
              <select className="in" value={s.arch} onChange={(e) => s.set({ arch: e.target.value as Settings['arch'] })} aria-label="Тип нейросети">
                <option value="Unet">Unet · универсальная, рекомендуется</option><option value="FPN">FPN · быстрее, границы грубее</option><option value="DeepLabV3Plus">DeepLabV3Plus · для крупных объектов</option>
              </select>
            </Field>
            <Field title="Размер «основы» сети" help="encoder">
              <select className="in" value={s.encoder} onChange={(e) => s.set({ encoder: e.target.value as Settings['encoder'] })} aria-label="Энкодер">
                <option value="resnet18">resnet18 · лёгкая и быстрая</option><option value="resnet34">resnet34 · компромисс</option><option value="resnet50">resnet50 · мощная и тяжёлая</option>
              </select>
            </Field>
            <Field title="Начать с готовых знаний" help="pretrained">
              <label className="toggle"><input type="checkbox" checked={s.pretrained} onChange={(e) => s.set({ pretrained: e.target.checked })} /><span>Использовать веса ImageNet (при первом запуске нужен интернет)</span></label>
            </Field>
            <Field title="Фото за один шаг (batch)" help="batch">
              <select className="in" style={{ maxWidth: 200 }} value={s.batch} onChange={num('batch')} aria-label="batch">
                {[1, 2, 4, 8, 16].map((b) => <option key={b}>{b}</option>)}
              </select>
            </Field>
            <Field title="Скорость обучения" help="lr">
              <select className="in" style={{ maxWidth: 200 }} value={s.lr} onChange={num('lr')} aria-label="Скорость обучения">
                {[0.0001, 0.0003, 0.0005, 0.001, 0.003, 0.01].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </Field>
            <Field title={`Вес Dice в ошибке: ${s.dice_w}`} help="dice">
              <input type="range" min={0} max={1} step={0.05} value={s.dice_w} onChange={num('dice_w')} aria-label="Вес Dice" />
            </Field>
            <Field title={`Порог уверенности: ${s.thr}`} help="thr">
              <input type="range" min={0.1} max={0.9} step={0.05} value={s.thr} onChange={num('thr')} aria-label="Порог уверенности" />
            </Field>
            <Field title="Случайное зерно (seed)" help="seed">
              <input className="in" type="number" style={{ maxWidth: 200, flex: 'none' }} value={s.seed} onChange={num('seed')} aria-label="seed" />
            </Field>
            <Field title="Где считать" help="device">
              <select className="in" value={s.device} onChange={(e) => s.set({ device: e.target.value as Settings['device'] })} aria-label="Устройство">
                <option value="auto">Авто (видеокарта, если есть)</option><option value="cpu">Только процессор</option>
              </select>
            </Field>
          </details>
        </div>
        <aside className="card flat" style={{ position: 'sticky', top: 20 }}>
          <h3 style={{ marginBottom: 12 }}>Что получится</h3>
          <div className="stack" style={{ gap: 12 }}>
            <div className="kpi"><b>{min < 90 ? `≈ ${min} мин` : `≈ ${(min / 60).toFixed(1)} ч`}</b><span>ориентировочное время на процессоре</span></div>
            <div className="kpi"><b style={{ fontSize: 22 }}>{s.img_size} × {s.img_size}</b><span>размер снимка при обучении</span></div>
            <div className="kpi"><b style={{ fontSize: 22 }}>{s.epochs} эпох</b><span>максимум проходов по всем фото</span></div>
            <div className="check warn" style={{ fontSize: 14 }}><span>i</span><div>Совет: за один запуск меняйте один параметр, тогда будет понятно, что повлияло на результат.</div></div>
          </div>
        </aside>
      </div>
      <div style={{ marginTop: 18 }}><ErrorBox text={err} /></div>
      <div className="pbar">
        <button className="btn" type="button" onClick={() => go('data')}>← Назад</button>
        {running
          ? <button className="btn primary big" type="button" onClick={() => go('train')}>Обучение уже идёт →</button>
          : <button className="btn primary big" type="button" onClick={begin} disabled={busy}>{busy ? 'Запускаем…' : 'Начать обучение'}</button>}
      </div>
    </section>
  );
}
