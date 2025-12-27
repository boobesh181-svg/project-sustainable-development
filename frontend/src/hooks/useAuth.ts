import { useState, useEffect, createContext, useContext, ReactNode, createElement, type ReactElement } from 'react';
import { apiClient } from '../services/api';

interface User {
  id: string;
  email: string;
  role: string;
  name?: string;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps): ReactElement => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Cookie-based session: probe /me on boot.
    void fetchUser();
  }, []);

  const fetchUser = async () => {
    try {
      const response = await apiClient.get('/api/v1/auth/me');
      setUser(response.data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    await apiClient.post('/api/v1/auth/login', {
      email,
      password,
    });

    await fetchUser();
  };

  const logout = () => {
    void apiClient.post('/api/v1/auth/logout');
    setUser(null);
  };

  const value: AuthContextType = {
    user,
    login,
    logout,
    loading,
    isAuthenticated: !!user,
  };

  return createElement(AuthContext.Provider, { value }, children);
};
