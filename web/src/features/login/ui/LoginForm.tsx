import { useState } from 'react';
import { useSession } from '@/entities/session/model/store';
import { ErrorBox } from '@/shared/ui/PageHead';

/** Экран входа: общий токен доступа, который выдаёт администратор сервера. */
export function LoginForm() {
  const login = useSession((s) => s.login);
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await login(token); }
    catch (x) { setErr(x instanceof Error ? x.message : 'Не удалось войти.'); }
    finally { setBusy(false); }
  };
  return (
    <main className="main" style={{ maxWidth: 460, margin: '0 auto' }}>
      <form className="card" onSubmit={(e) => void submit(e)}>
        <h1 style={{ marginTop: 0 }}>Ржавчина на листьях</h1>
        <p className="muted">Введите токен доступа. Его выдаёт администратор сервиса.</p>
        <div className="field">
          <input className="in" type="password" autoComplete="current-password" value={token} autoFocus
            onChange={(e) => setToken(e.target.value)} aria-label="Токен доступа" />
        </div>
        <ErrorBox text={err} />
        <div className="pbar"><span /><button className="btn primary big" type="submit" disabled={busy || !token.trim()}>{busy ? 'Входим…' : 'Войти'}</button></div>
      </form>
    </main>
  );
}
