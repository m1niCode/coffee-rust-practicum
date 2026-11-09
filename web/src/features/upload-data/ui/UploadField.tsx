import { useRef, useState } from 'react';
import { upload } from '@/shared/api/client';
import { HelpButton } from '@/shared/ui/help';
import type { HelpKey } from '@/shared/config/help';
import type { UploadResult } from '@/shared/api/types';

interface Props {
  kind: 'train' | 'valid' | 'test' | 'auto';
  title: string;
  hint: string;
  help?: HelpKey;
  optional?: boolean;
  /** Подпись под полем после загрузки: сколько файлов принял сервер. */
  onDone: () => void;
  onClear?: () => Promise<void>;
}

/** Выбор файлов (фото, маски или zip) и их отправка на сервер. */
export function UploadField({ kind, title, hint, help, optional, onDone, onClear }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [share, setShare] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const send = async (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (!files.length) return;
    setBusy(true); setErr(null); setMsg(null); setShare(0);
    const fd = new FormData();
    fd.append('kind', kind);
    files.forEach((f) => fd.append('files', f));
    try {
      const r = await upload<UploadResult>('/data/upload', fd, setShare);
      const n = r.saved.train + r.saved.valid + r.saved.test;
      setMsg(`Загружено файлов: ${n}${r.skipped ? `, пропущено лишних: ${r.skipped}` : ''}.`);
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Не удалось загрузить файлы.');
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  };

  const clear = async () => {
    if (!onClear) return;
    setErr(null); setMsg(null);
    try { await onClear(); } catch (e) { setErr(e instanceof Error ? e.message : 'Не удалось очистить.'); }
  };

  return (
    <div className="field">
      <div className="lbl">
        {title} {optional && <span className="chip mute">необязательно</span>}
        {help && <HelpButton topic={help} />}
      </div>
      <div className="hint">{hint}</div>
      <div className="path">
        <input ref={input} type="file" multiple accept=".zip,.jpg,.jpeg,.png" hidden aria-label={title}
          onChange={(e) => void send(e.target.files)} />
        <button className="btn" type="button" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? `Загружаем… ${Math.round(share * 100)}%` : 'Выбрать файлы или zip…'}
        </button>
        {onClear && <button className="btn" type="button" disabled={busy} onClick={() => void clear()}>Очистить</button>}
      </div>
      {msg && <div className="hint" style={{ color: 'var(--ok)' }}>{msg}</div>}
      {err && <div className="hint" style={{ color: 'var(--rust)' }}>{err}</div>}
    </div>
  );
}
