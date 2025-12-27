import React, { useEffect } from 'react';
import { Navigate } from 'react-router-dom';

import { logout } from '../services/api';
import { useAuth } from '../state/AuthContext';

export const LogoutPage: React.FC = () => {
  const { clear } = useAuth();

  useEffect(() => {
    (async () => {
      try {
        await logout();
      } finally {
        clear();
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <Navigate to="/login" replace />;
};
