import { useState } from 'react';
import { bestOf, useExperiments } from '@/entities/experiment/model/store';
import { post } from '@/shared/api/client';
import { go } from '@/shared/lib/route';
import { pct, verdict } from '@/shared/lib/format';
import { useAnalyze } from '@/features/analyze-photos/model/store';
import { LineChart } from '@/shared/ui/LineChart';
import { ErrorBox, PageHead } from '@/shared/ui/PageHead';

const COLORS = ['--s1', '--s2', '--s3'];
const score = (e: { test_iou: number | null; best_val_iou: number | null }) => e.test_iou ?? e.best_val_iou;

export function ResultsPage() {
  const { items, error } = useExperiments();
  const setModel = useAnalyze((s) => s.setExperiment);
  const [off, setOff] = useState<Set<string>>(new Set());
  const [msg, setMsg] = useState<string | null>(null);

  if (items.length === 0) {
    return (
      <section>
        <PageHead step="Шаг 4 из 4" title="Результаты и сравнение" />
        <ErrorBox text={error} />
        <div className="card empty"><p className="muted">Экспериментов пока нет. Обучите модель, и её результаты появятся здесь.</p>
          <button className="btn primary" type="button" onClick={() => go('data')}>Обучить модель</button></div>
      </section>
    );
  }

  const best = bestOf(items);
  const shown = items.filter((e) => !off.has(e.id));
  const xmax = Math.max(2, ...shown.map((e) => e.curves.val_iou.length));
  const toggle = (id: string) => setOff((o) => { const n = new Set(o); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const openFolder = async (id: string) => {
    try { await post(`/experiments/${encodeURIComponent(id)}/open-folder`); }
    catch (e) { setMsg(e instanceof Error ? e.message : 'Не удалось открыть папку.'); }
  };

  return (
    <section>
      <PageHead step="Шаг 4 из 4" title="Результаты и сравнение">
        Отметьте эксперименты, которые хотите сравнить. Выше значение «совпадение с разметкой» — модель точнее находит ржавчину.
      </PageHead>
      <div className="card">
        <div className="tbl-wrap">
          <table>
            <thead><tr><th>Сравнить</th><th>Эксперимент</th><th>Модель</th><th className="num">Размер</th><th className="num">Эпох</th><th className="num">Совпадение</th><th>Оценка</th></tr></thead>
            <tbody>
              {items.map((e) => { const v = verdict(score(e)); return (
                <tr key={e.id}>
                  <td><label className="toggle"><input type="checkbox" checked={!off.has(e.id)} onChange={() => toggle(e.id)} aria-label={`Сравнить ${e.id}`} /></label></td>
                  <td><b>{e.id}</b> {best?.id === e.id && <span className="chip">лучший</span>}</td>
                  <td>{e.arch} · {e.encoder}</td>
                  <td className="num mono">{e.image_size ?? '—'}</td>
                  <td className="num mono">{e.epochs_done}{e.epochs_planned ? ` из ${e.epochs_planned}` : ''}</td>
                  <td className="num mono"><b>{pct(score(e))}</b></td>
                  <td><span className={'chip' + (v.tone === 'warn' ? ' warn' : '')}>{v.text}</span></td>
                </tr>
              ); })}
            </tbody>
          </table>
        </div>
      </div>
      <div className="grid2" style={{ marginTop: 18, gridTemplateColumns: 'minmax(0,1.5fr) minmax(0,1fr)', alignItems: 'start' }}>
        <div className="card">
          <h3>Как росло качество по эпохам</h3>
          <LineChart label="Сравнение экспериментов" xmax={xmax} ymin={0} ymax={1} percent
            series={shown.map((e) => ({ data: e.curves.val_iou, color: COLORS[items.indexOf(e) % COLORS.length] ?? '--s1' }))} />
          <div className="legend">
            {shown.map((e) => <span key={e.id}><i style={{ background: `var(${COLORS[items.indexOf(e) % COLORS.length] ?? '--s1'})` }} />{e.id} · {e.encoder}, {e.image_size}px</span>)}
            {shown.length === 0 && <span className="muted">Отметьте хотя бы один эксперимент</span>}
          </div>
        </div>
        {best && (
          <div className="card">
            <h3>Лучшая модель: {best.id}</h3>
            <div className="kpi" style={{ margin: '14px 0' }}>
              <b style={{ color: 'var(--accent)', fontSize: 40 }}>{pct(score(best))}</b>
              <span>совпадение с разметкой эксперта{best.test_images ? ` на ${best.test_images} тестовых фото` : ' на проверочных фото'}</span>
            </div>
            {best.test_dice != null && <div className="kpi" style={{ marginBottom: 14 }}><b style={{ fontSize: 24 }}>{pct(best.test_dice)}</b><span>точность выделения (Dice)</span></div>}
            <p className="muted" style={{ fontSize: 14, marginBottom: 16 }}>{best.arch}, {best.encoder}, снимки {best.image_size}px, {best.epochs_done} эпох.</p>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button className="btn primary" type="button" disabled={!best.has_model} onClick={() => { setModel(best.id); go('check'); }}>Применить к фото</button>
              <button className="btn" type="button" onClick={() => void openFolder(best.id)}>Открыть папку</button>
            </div>
            <div style={{ marginTop: 12 }}><ErrorBox text={msg} /></div>
          </div>
        )}
      </div>
    </section>
  );
}
