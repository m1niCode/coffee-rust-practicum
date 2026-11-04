import { useEffect, useRef } from 'react';
import { create } from 'zustand';
import { HELP, type HelpKey } from '@/shared/config/help';

const useHelp = create<{ key: HelpKey | null; open: (k: HelpKey) => void; close: () => void }>((set) => ({
  key: null,
  open: (key) => set({ key }),
  close: () => set({ key: null }),
}));

/** Кнопка «!» рядом с параметром. */
export function HelpButton({ topic }: { topic: HelpKey }) {
  const open = useHelp((s) => s.open);
  return (
    <button type="button" className="help" aria-label={`Подсказка: ${HELP[topic][0]}`} onClick={() => open(topic)}>
      !
    </button>
  );
}

/** Окно подсказки. Один раз монтируется в корне приложения. */
export function HelpModal() {
  const { key, close } = useHelp();
  const ok = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!key) return;
    ok.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && close();
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [key, close]);
  if (!key) return null;
  const [title, text] = HELP[key];
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-labelledby="help-title" onClick={close}>
      <div className="box" onClick={(e) => e.stopPropagation()}>
        <h3 id="help-title">{title}</h3>
        <p>{text}</p>
        <button ref={ok} type="button" className="btn primary" style={{ alignSelf: 'flex-end' }} onClick={close}>
          Понятно
        </button>
      </div>
    </div>
  );
}
