import React from 'react';
import { useTheme } from '../../context/ThemeContext';
import { AudioPlayer, AudioPlayerProps } from './index';

// Componente adaptador que conecta o sistema de temas do app com o AudioPlayer
export const AudioPlayerAdapter: React.FC<Omit<AudioPlayerProps, 'theme' | 'isDarkMode'>> = (props) => {
  const { colors, isDarkTheme, theme } = useTheme();
  
  // Adaptar o tema para o formato esperado pelo AudioPlayer
  const adaptedTheme = {
    colors: {
      primary: colors.primary,
      onPrimary: '#ffffff',
      surface: colors.background.secondary,
      onSurface: colors.text.primary,
      background: colors.background.primary,
      outline: colors.border,
      inverseSurface: colors.text.primary,
      inverseOnSurface: colors.background.primary,
      errorContainer: colors.error + '20',
      onErrorContainer: colors.error,
      shadow: '#000000',
    }
  };
  
  return (
    <AudioPlayer
      {...props}
      theme={adaptedTheme}
      isDarkMode={isDarkTheme}
    />
  );
};

export default AudioPlayerAdapter;