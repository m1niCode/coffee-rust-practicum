import { create } from 'zustand';
import { api, post, setUnauthorizedHandler } from '@/shared/api/client';

interface AuthState {
  required: boolean;
  authed: boolean;
}

interface State {
  checked: boolean;
  required: boolean;
  authed: boolean;
  check: () => Promise<void>;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const useSession = create<State>((set) => {
  setUnauthorizedHandler(() => set({ authed: false }));
  return {
    checked: false, required: false, authed: true,
    check: async () => {
      const s = await api<AuthState>('/auth');
      set({ checked: true, required: s.required, authed: s.authed });
    },
    login: async (token) => {
      await post('/login', { token });
      set({ authed: true });
    },
    logout: async () => {
      await post('/logout');
      set({ authed: false });
    },
  };
});
