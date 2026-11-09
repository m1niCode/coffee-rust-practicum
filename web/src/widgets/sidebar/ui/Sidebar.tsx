import { ThemeToggle } from '@/features/theme-toggle/ui/ThemeToggle';
import { useSession } from '@/entities/session/model/store';
import { useExperiments } from '@/entities/experiment/model/store';
import { go, type Route } from '@/shared/lib/route';

const Item = ({ to, cur, n, children }: { to: Route; cur: Route; n?: number; children: string }) => (
  <button type="button" className="nav" aria-current={cur === to ? 'page' : undefined} onClick={() => go(to)}>
    {n ? <span className="n">{n}</span> : null}
    {children}
  </button>
);

export function Sidebar({ route }: { route: Route }) {
  const info = useExperiments((s) => s.info);
  const device = info?.device;
  const { required, logout } = useSession();
  return (
    <aside className="side" aria-label="Навигация">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 19C5 10 10 5 20 4c0 10-5 15-14 15" /><path d="M5 19c3-5 6-8 10-10" />
          </svg>
        </div>
        <div><b>Ржавчина на листьях</b><span>Кофе · анализ по фото</span></div>
      </div>
      <Item to="home" cur={route}>Главная</Item>
      <div className="grp">Обучить модель</div>
      <Item to="data" cur={route} n={1}>Данные</Item>
      <Item to="params" cur={route} n={2}>Параметры</Item>
      <Item to="train" cur={route} n={3}>Обучение</Item>
      <Item to="results" cur={route} n={4}>Результаты</Item>
      <div className="grp">Применить</div>
      <Item to="check" cur={route}>Проверить фото</Item>
      <div className="side-foot">
        <div className="row hide-m">
          <span>Вычисления</span>
          <span className="chip mute">{device === 'cuda' ? 'Видеокарта' : 'Процессор'}</span>
        </div>
        {info?.gpu_name && <div className="muted hide-m" style={{ fontSize: 12 }}>{info.gpu_name}, {info.gpu_memory_gb} ГБ</div>}
        <ThemeToggle />
        {required && <button className="btn" type="button" onClick={() => void logout()}>Выйти</button>}
      </div>
    </aside>
  );
}
