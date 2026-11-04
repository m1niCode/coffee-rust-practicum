import { useExperiments } from '@/entities/experiment/model/store';
import { go } from '@/shared/lib/route';
import { pct } from '@/shared/lib/format';
import { PageHead } from '@/shared/ui/PageHead';

export function HomePage() {
  const items = useExperiments((s) => s.items);
  return (
    <section>
      <PageHead title="Что будем делать?">
        Научите программу находить ржавчину на фотографиях листьев кофе или сразу проверьте свои снимки готовой моделью.
      </PageHead>
      <div className="grid2">
        <button className="start" type="button" onClick={() => go('data')}>
          <div className="ic">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12M7 10l5 5 5-5M4 20h16" /></svg>
          </div>
          <h2>Обучить модель</h2>
          <p className="muted">Покажите программе фото с отмеченной ржавчиной, и она научится находить её сама.</p>
          <div className="steps"><span>Данные</span><span>Параметры</span><span>Обучение</span><span>Результаты</span></div>
          <div className="go">Начать →</div>
        </button>
        <button className="start alt" type="button" onClick={() => go('check')}>
          <div className="ic">
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="11" r="2" /><path d="M21 16l-5-4-8 7" /></svg>
          </div>
          <h2>Проверить фото</h2>
          <p className="muted">Загрузите снимки листьев и получите долю поражённой площади по каждому кадру.</p>
          <div className="steps"><span>Выбрать модель</span><span>Загрузить фото</span><span>Смотреть и сохранить</span></div>
          <div className="go" style={{ color: 'var(--rust)' }}>Проверить →</div>
        </button>
      </div>
      <div className="card" style={{ marginTop: 22 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
          <h2>Ваши эксперименты</h2>
          {items.length > 0 && <button className="btn ghost" type="button" onClick={() => go('results')}>Сравнить →</button>}
        </div>
        {items.length === 0 ? (
          <div className="empty"><p className="muted">Пока нет ни одного эксперимента. Обучите первую модель, и она появится здесь.</p></div>
        ) : (
          <div className="tbl-wrap">
            <table>
              <thead><tr><th>Эксперимент</th><th>Сеть</th><th className="num">Размер</th><th className="num">Эпох</th><th className="num">Совпадение</th></tr></thead>
              <tbody>
                {items.map((e) => (
                  <tr key={e.id} className="pick" onClick={() => go('results')}>
                    <td><b>{e.id}</b></td><td>{e.arch} · {e.encoder}</td>
                    <td className="num mono">{e.image_size ?? '—'}</td><td className="num mono">{e.epochs_done}</td>
                    <td className="num mono"><b>{pct(e.test_iou ?? e.best_val_iou)}</b></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
