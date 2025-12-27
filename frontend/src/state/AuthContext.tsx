import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { fetchMe, UserMe } from '../services/api';

type AuthState = {
  booted: boolean;
  user: UserMe | null;
  refresh: () => Promise<void>;
  clear: () => void;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [booted, setBooted] = useState(false);
  const [user, setUser] = useState<UserMe | null>(null);

  const refresh = async () => {
    try {
      const me = await fetchMe();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setBooted(true);
    }
  };

  const clear = () => setUser(null);

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo(() => ({ booted, user, refresh, clear }), [booted, user]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
