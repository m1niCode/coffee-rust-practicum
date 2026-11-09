import { useEffect, useState } from 'react';
import { useExperiments } from '@/entities/experiment/model/store';
import { useAnalyze } from '@/features/analyze-photos/model/store';
import { apiUrl } from '@/shared/api/client';
import { go } from '@/shared/lib/route';
import { pct, pct1 } from '@/shared/lib/format';
import { HelpButton } from '@/shared/ui/help';
import { ErrorBox, PageHead } from '@/shared/ui/PageHead';

export function CheckPage() {
  const items = useExperiments((s) => s.items).filter((e) => e.has_model);
  const a = useAnalyze();
  const [i, setI] = useState(0);
  const [over, setOver] = useState(false);
  const [changed, setChanged] = useState(false);

  useEffect(() => {
    if (!a.experiment && items[0]) a.setExperiment(items[0].id);
  }, [a, items]);
  useEffect(() => { setI(0); setChanged(false); }, [a.session]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      const n = a.results.length;
      if (e.key === 'ArrowRight') setI((v) => Math.min(n - 1, v + 1));
      if (e.key === 'ArrowLeft') setI((v) => Math.max(0, v - 1));
    };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [a.results.length]);

  const pick = (list: FileList | null) => {
    const files = Array.from(list ?? []).filter((f) => /\.jpe?g$/i.test(f.name));
    if (files.length) void a.analyze(files);
  };
  const f = a.results[i];
  const on = f ? Math.round((f.rust_pred_pct / 100) * 400) : 0;

  return (
    <section>
      <PageHead title="Проверить фото">
        Загрузите снимки листьев. Программа покажет, где найдена ржавчина и какую долю площади она занимает.
      </PageHead>
      {items.length === 0 ? (
        <div className="card empty"><p className="muted">Нет обученных моделей. Сначала обучите модель, затем вернитесь сюда.</p>
          <button className="btn primary" type="button" onClick={() => go('data')}>Обучить модель</button></div>
      ) : (
        <div className="grid2" style={{ gridTemplateColumns: 'minmax(0,320px) minmax(0,1fr)', alignItems: 'start' }}>
          <div className="stack">
            <div className="card">
              <div className="field" style={{ paddingTop: 0 }}>
                <div className="lbl">Модель</div>
                <select className="in" value={a.experiment} onChange={(e) => { a.setExperiment(e.target.value); setChanged(true); }} aria-label="Модель">
                  {items.map((e) => <option key={e.id} value={e.id}>{e.id.replace(/^shared:/, '')}{e.shared ? ' (готовая)' : ''} · {pct(e.test_iou ?? e.best_val_iou)} · {e.encoder}</option>)}
                </select>
              </div>
              <div className="field" style={{ border: 0, paddingBottom: 0 }}>
                <div className="lbl">Чувствительность: {a.threshold}<HelpButton topic="thr" /></div>
                <input type="range" min={0.1} max={0.9} step={0.05} value={a.threshold} aria-label="Чувствительность"
                  onChange={(e) => { a.setThreshold(Number(e.target.value)); setChanged(true); }} />
                <div className="hint" style={{ display: 'flex', justifyContent: 'space-between' }}><span>находит больше, чаще ошибается</span><span>осторожнее</span></div>
                {changed && a.results.length > 0 && <button className="btn" type="button" onClick={() => void a.analyze([])} disabled={a.busy}>Пересчитать</button>}
              </div>
            </div>
            <label className={'dz' + (over ? ' over' : '')}
              onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files); }}>
              <input type="file" multiple accept="image/jpeg" onChange={(e) => { pick(e.target.files); e.target.value = ''; }} />
              {a.busy ? <span className="spin" /> : (
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V4M7 9l5-5 5 5M4 20h16" /></svg>
              )}
              <b>{a.busy ? 'Обрабатываем…' : 'Перетащите фото сюда'}</b>
              <span className="muted">или нажмите, чтобы выбрать файлы .jpg</span>
            </label>
            {a.session && <a className="btn" href={apiUrl(`/inference/${a.session}/results.csv`)}>Сохранить таблицу (CSV)</a>}
            <ErrorBox text={a.error} />
          </div>
          <div className="stack" style={{ minWidth: 0 }}>
            {!f ? (
              <div className="card empty"><p className="muted">Здесь появится результат. Загрузите хотя бы одно фото.</p></div>
            ) : (
              <>
                <div className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 14 }}>
                    <h2>Кадр {i + 1} из {a.results.length}</h2>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn" type="button" aria-label="Предыдущий" disabled={i === 0} onClick={() => setI(i - 1)}>←</button>
                      <button className="btn" type="button" aria-label="Следующий" disabled={i === a.results.length - 1} onClick={() => setI(i + 1)}>→</button>
                    </div>
                  </div>
                  <div className="pair">
                    <figure><div className="img"><img src={f.photo} alt="Исходное фото листа" /></div><figcaption>{f.file}</figcaption></figure>
                    <figure><div className="img"><img src={f.overlay} alt="Лист с выделенной ржавчиной" /></div><figcaption>Найденная ржавчина <span className="chip rust">контур</span></figcaption></figure>
                  </div>
                  {a.results.length > 1 && (
                    <div className="thumbs" style={{ marginTop: 14 }}>
                      {a.results.map((r, k) => <button key={k} type="button" aria-pressed={k === i} aria-label={`Кадр ${k + 1}`} onClick={() => setI(k)}><img src={r.photo} alt="" /></button>)}
                    </div>
                  )}
                </div>
                <div className="card">
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 22, alignItems: 'center' }}>
                    <div>
                      <div className="kpi"><b style={{ fontSize: 44, color: 'var(--rust)' }}>{pct1(f.rust_pred_pct)}</b><span>площади листа поражено ржавчиной</span></div>
                      {f.rust_true_pct != null && <div className="muted" style={{ marginTop: 10, fontSize: 14 }}>По разметке эксперта: {pct1(f.rust_true_pct)}</div>}
                    </div>
                    <div>
                      <div className="cells" aria-hidden="true">{Array.from({ length: 400 }, (_, k) => <i key={k} className={k < on ? 'on' : ''} />)}</div>
                      <div className="muted" style={{ fontSize: 13, marginTop: 8 }}>Лист разделён на 400 долей. Оранжевые — поражённые.</div>
                    </div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 14, marginTop: 20, paddingTop: 18, borderTop: '1px solid var(--line)' }}>
                    <div className="kpi"><b style={{ fontSize: 22 }}>{pct(f.mean_confidence)}</b><span>уверенность модели</span></div>
                    {f.IoU != null && <div className="kpi"><b style={{ fontSize: 22 }}>{pct(f.IoU)}</b><span>совпадение с разметкой эксперта</span></div>}
                    <div className="kpi"><b style={{ fontSize: 22 }}>{f.width} × {f.height}</b><span>размер снимка, px</span></div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
