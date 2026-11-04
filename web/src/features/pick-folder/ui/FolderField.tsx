import { useState } from 'react';
import { post } from '@/shared/api/client';
import { HelpButton } from '@/shared/ui/help';
import type { HelpKey } from '@/shared/config/help';

interface Props {
  title: string;
  hint: string;
  help: HelpKey;
  optional?: boolean;
  value: string;
  onChange: (v: string) => void;
}

/** Поле пути с кнопкой «Обзор…»: окно выбора папки открывает Python-сервер. */
export function FolderField({ title, hint, help, optional, value, onChange }: Props) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const browse = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await post<{ path: string }>('/browse-folder');
      if (r.path) onChange(r.path);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Не удалось открыть окно выбора папки.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="field">
      <div className="lbl">
        {title} {optional && <span className="chip mute">необязательно</span>}
        <HelpButton topic={help} />
      </div>
      <div className="hint">{hint}</div>
      <div className="path">
        <input className="in" value={value} onChange={(e) => onChange(e.target.value)} aria-label={title} spellCheck={false} />
        <button className="btn" type="button" onClick={browse} disabled={busy}>{busy ? 'Выбираем…' : 'Обзор…'}</button>
      </div>
      {err && <div className="hint" style={{ color: 'var(--rust)' }}>{err}</div>}
    </div>
  );
}
