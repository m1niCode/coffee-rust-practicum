import type { ReactNode } from 'react';

export function PageHead({ step, title, children }: { step?: string; title: string; children?: ReactNode }) {
  return (
    <div className="head">
      {step && <span className="chip" style={{ width: 'max-content' }}>{step}</span>}
      <h1>{title}</h1>
      {children && <p>{children}</p>}
    </div>
  );
}

export function ErrorBox({ text }: { text: string | null }) {
  return text ? <div className="err" role="alert">{text}</div> : null;
}
