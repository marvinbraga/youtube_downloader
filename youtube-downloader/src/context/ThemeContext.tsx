
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useColorScheme } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { themes } from '../styles/theme';

// Chave para armazenar preferência de tema
const THEME_PREFERENCE_KEY = '@theme_preference';

// Tipo para o tema
type ThemeMode = 'light' | 'dark' | 'system';

// Contexto do tema
type ThemeContextType = {
  themeMode: ThemeMode;
  isDarkTheme: boolean;
  colors: any;
  toggleTheme: () => void;
  setThemeMode: (mode: ThemeMode) => void;
  theme: any; // Tema completo incluindo cores e outras propriedades
};

// Criar o contexto
const ThemeContext = createContext<ThemeContextType>({
  themeMode: 'system',
  isDarkTheme: true,
  colors: themes.dark.colors,
  theme: themes.dark,
  toggleTheme: () => {},
  setThemeMode: () => {},
});

// Hook para usar o tema
export const useTheme = () => useContext(ThemeContext);

// Provider do tema
export const ThemeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Estado para o modo de tema
  const [themeMode, setThemeMode] = useState<ThemeMode>('system');
  
  // Obter o tema do sistema
  const colorScheme = useColorScheme();
  
  // Determinar se o tema é escuro com base no modo e no tema do sistema
  const isDarkTheme = 
    themeMode === 'system' 
      ? colorScheme === 'dark' 
      : themeMode === 'dark';
  
  // Selecionar o tema completo baseado na preferência
  const currentTheme = isDarkTheme ? themes.dark : themes.light;
  
  // Cores baseadas no tema atual
  const colors = currentTheme.colors;
  
  // Alternar entre temas
  const toggleTheme = () => {
    const newMode: ThemeMode = themeMode === 'light' ? 'dark' : 'light';
    setThemeMode(newMode);
    saveThemePreference(newMode);
  };
  
  // Definir modo de tema específico
  const setThemeModeAndSave = (mode: ThemeMode) => {
    setThemeMode(mode);
    saveThemePreference(mode);
  };
  
  // Salvar preferência de tema
  const saveThemePreference = async (mode: ThemeMode) => {
    try {
      await AsyncStorage.setItem(THEME_PREFERENCE_KEY, mode);
    } catch (error) {
      console.error('Erro ao salvar preferência de tema:', error);
    }
  };
  
  // Carregar preferência de tema ao iniciar
  useEffect(() => {
    const loadThemePreference = async () => {
      try {
        const savedTheme = await AsyncStorage.getItem(THEME_PREFERENCE_KEY);
        if (savedTheme) {
          setThemeMode(savedTheme as ThemeMode);
        }
      } catch (error) {
        console.error('Erro ao carregar preferência de tema:', error);
      }
    };
    
    loadThemePreference();
  }, []);
  
  // Valor do contexto
  const contextValue: ThemeContextType = {
    themeMode,
    isDarkTheme,
    colors,
    theme: currentTheme,
    toggleTheme,
    setThemeMode: setThemeModeAndSave,
  };
  
  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  );
};
