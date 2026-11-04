import { useState } from 'react';
import { post } from '@/shared/api/client';
import type { DataCheck, FolderInfo } from '@/shared/api/types';
import { ErrorBox } from '@/shared/ui/PageHead';

interface Props {
  train: string;
  valid: string;
  test: string;
}

const Row = ({ ok, warn, children }: { ok?: boolean; warn?: boolean; children: React.ReactNode }) => (
  <div className={'check' + (warn || !ok ? ' warn' : '')}>
    <span style={{ color: ok ? 'var(--ok)' : 'var(--warn)' }}>{ok ? '✓' : '!'}</span>
    <div>{children}</div>
  </div>
);

const line = (name: string, f: FolderInfo, needMask: boolean) => {
  if (!f.exists) return <Row>{name}: папка не найдена.</Row>;
  if (needMask) {
    return f.pairs > 0
      ? <Row ok><b>{name}:</b> найдено {f.pairs} пар «фото + маска».</Row>
      : <Row><b>{name}:</b> нет пар «фото .jpg + маска .png». Проверьте, что маска называется так же, как фото.</Row>;
  }
  return <Row ok><b>{name}:</b> {f.photos} фото, из них с масками {f.pairs}. {f.pairs ? 'Итоговая оценка будет посчитана.' : 'Будет посчитана только доля поражения.'}</Row>;
};

export function CheckData({ train, valid, test }: Props) {
  const [res, setRes] = useState<DataCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = async () => {
    setBusy(true); setErr(null);
    try { setRes(await post<DataCheck>('/data/check', { train, valid, test })); }
    catch (e) { setErr(e instanceof Error ? e.message : 'Не удалось проверить данные.'); }
    finally { setBusy(false); }
  };
  return (
    <div>
      <button className="btn" type="button" onClick={run} disabled={busy}>
        {busy ? <><span className="spin" /> Проверяем…</> : 'Проверить данные'}
      </button>
      <div className="stack" style={{ marginTop: 16 }}>
        <ErrorBox text={err} />
        {res && (
          <>
            {line('Для обучения', res.train, true)}
            {line('Для проверки', res.valid, true)}
            {test.trim() ? line('Для итоговой оценки', res.test, false) : <Row ok>Папка test не задана: итоговая оценка будет пропущена.</Row>}
            {res.duplicates_count > 0
              ? <Row>Одинаковые имена файлов есть и в train, и в valid ({res.duplicates_count} шт.). Оценка качества получится завышенной.</Row>
              : res.ok && <Row ok>Одинаковых снимков в train и valid не найдено.</Row>}
            {res.rust_share_train != null && <Row ok>Ржавчина занимает в среднем {(res.rust_share_train * 100).toFixed(1).replace('.', ',')}% площади на масках train.</Row>}
          </>
        )}
      </div>
    </div>
  );
}
