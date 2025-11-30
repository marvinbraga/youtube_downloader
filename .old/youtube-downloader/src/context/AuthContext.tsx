
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { authenticate } from '../services/api';
import { AuthState } from '../types';

interface AuthContextData {
  authState: AuthState;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextData>({} as AuthContextData);

export const useAuth = () => useContext(AuthContext);

export const AuthProvider: React.FC<{children: ReactNode}> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    token: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  // Verificar se já existe um token salvo
  useEffect(() => {
    loadToken();
  }, []);

  const loadToken = async () => {
    try {
      const token = await AsyncStorage.getItem('@auth_token');
      if (token) {
        setAuthState({
          token,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
        
        // Configurar timer para renovar o token automaticamente (a cada 25 minutos)
        const refreshTimer = setTimeout(() => {
          login();
        }, 25 * 60 * 1000);
        
        return () => clearTimeout(refreshTimer);
      } else {
        setAuthState({
          token: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      }
    } catch (error) {
      setAuthState({
        token: null,
        isAuthenticated: false,
        isLoading: false,
        error: 'Erro ao carregar token',
      });
    }
  };

  const login = async () => {
    try {
      setAuthState({
        ...authState,
        isLoading: true,
        error: null,
      });

      const token = await authenticate();

      setAuthState({
        token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (error) {
      setAuthState({
        token: null,
        isAuthenticated: false,
        isLoading: false,
        error: 'Falha na autenticação',
      });
    }
  };

  const logout = async () => {
    try {
      await AsyncStorage.removeItem('@auth_token');
      setAuthState({
        token: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    } catch (error) {
      setAuthState({
        ...authState,
        error: 'Erro ao fazer logout',
      });
    }
  };

  return (
    <AuthContext.Provider value={{ authState, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
