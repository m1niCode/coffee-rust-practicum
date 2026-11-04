import { useExperiments } from '@/entities/experiment/model/store';
import { useTraining } from '@/entities/training/model/store';
import { go } from '@/shared/lib/route';
import { minutes, pct } from '@/shared/lib/format';
import { LineChart } from '@/shared/ui/LineChart';
import { ErrorBox, PageHead } from '@/shared/ui/PageHead';

export function TrainPage() {
  const t = useTraining();
  const reload = useExperiments((s) => s.load);

  if (t.status === 'idle') {
    return (
      <section>
        <PageHead step="Шаг 3 из 4" title="Обучение не запущено" />
        <div className="card empty">
          <p className="muted">Выберите данные и параметры, затем нажмите «Начать обучение».</p>
          <button className="btn primary" type="button" onClick={() => go('data')}>Перейти к данным</button>
        </div>
      </section>
    );
  }

  const total = t.totalEpochs || 1;
  const last = t.epochs[t.epochs.length - 1];
  const best = t.epochs.reduce((m, e) => Math.max(m, e.val_iou), 0);
  const finished = t.status === 'done' || t.status === 'error';
  const title = t.status === 'done' ? 'Обучение завершено'
    : t.status === 'error' ? 'Обучение прервано ошибкой'
    : t.status === 'stopping' ? 'Останавливаем…' : 'Модель учится';
  const epochNow = Math.min(total, last ? last.epoch : 0);

  return (
    <section>
      <PageHead step="Шаг 3 из 4" title={title}>
        Окно можно не закрывать и заняться другим. Лучшая версия сохраняется автоматически.
      </PageHead>
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'end', marginBottom: 12 }}>
          <div className="kpi">
            <b>{t.status === 'done' ? `Готово: ${t.epochs.length} эпох` : `Эпоха ${epochNow} из ${total}`}</b>
            <span>{finished ? (t.status === 'done' ? 'Результаты сохранены' : 'Подробности в журнале ниже') : `Осталось ${minutes(t.etaSeconds)}`}</span>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {!finished && <button className="btn danger" type="button" onClick={() => void t.stop()} disabled={t.status === 'stopping'}>Остановить</button>}
            {t.status === 'done' && <button className="btn primary" type="button" onClick={() => { void reload(); go('results'); }}>Смотреть результаты →</button>}
          </div>
        </div>
        <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(t.progress * 100)}>
          <i style={{ width: `${Math.round(t.progress * 100)}%` }} />
        </div>
      </div>
      {t.error && <div style={{ marginTop: 18 }}><ErrorBox text={t.error} /></div>}
      <div className="grid3" style={{ marginTop: 18 }}>
        <div className="card flat kpi"><b style={{ color: 'var(--accent)' }}>{last ? pct(last.val_iou) : '—'}</b><span>совпадение с разметкой сейчас</span></div>
        <div className="card flat kpi"><b>{last ? pct(best) : '—'}</b><span>лучший результат за всё время</span></div>
        <div className="card flat kpi"><b>{last ? last.val_loss.toFixed(3) : '—'}</b><span>ошибка на проверочных фото (меньше — лучше)</span></div>
      </div>
      <div className="grid2" style={{ marginTop: 18 }}>
        <div className="card">
          <h3>Совпадение с разметкой <span className="muted" style={{ fontWeight: 400 }}>(больше — лучше)</span></h3>
          <LineChart label="Качество по эпохам" xmax={total} ymin={0} ymax={1} percent series={[{ data: t.epochs.map((e) => e.val_iou), color: '--s1' }]} />
        </div>
        <div className="card">
          <h3>Ошибка модели <span className="muted" style={{ fontWeight: 400 }}>(меньше — лучше)</span></h3>
          <LineChart label="Ошибка по эпохам" xmax={total} ymin={0} ymax={Math.max(0.5, ...t.epochs.map((e) => Math.max(e.train_loss, e.val_loss)))}
            series={[{ data: t.epochs.map((e) => e.train_loss), color: '--s1' }, { data: t.epochs.map((e) => e.val_loss), color: '--s2' }]} />
          <div className="legend"><span><i style={{ background: 'var(--s1)' }} />на фото для обучения</span><span><i style={{ background: 'var(--s2)' }} />на фото для проверки</span></div>
        </div>
      </div>
      <div className="card" style={{ marginTop: 18 }}>
        <h3 style={{ marginBottom: 10 }}>Журнал</h3>
        <div className="log">{t.log.slice(-8).map((l, i) => <div key={i}>{l}</div>)}</div>
      </div>
    </section>
  );
}
