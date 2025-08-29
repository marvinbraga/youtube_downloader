import React, { memo, useMemo } from 'react';
import { useTheme } from '../../context/ThemeContext';
import { AudioPlayer, AudioPlayerProps } from './index';

// Componente adaptador otimizado com memoização
const AudioPlayerAdapter: React.FC<Omit<AudioPlayerProps, 'theme' | 'isDarkMode'>> = (props) => {
  const { colors, isDarkTheme, theme } = useTheme();
  
  // Memoizar tema adaptado para evitar recriação desnecessária
  const adaptedTheme = useMemo(() => ({
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
  }), [colors, isDarkTheme]);
  
  return (
    <AudioPlayer
      {...props}
      theme={adaptedTheme}
      isDarkMode={isDarkTheme}
    />
  );
};

// Comparação para React.memo - só re-renderiza se áudio ou propriedades relevantes mudaram
const arePropsEqual = (prevProps: any, nextProps: any) => {
  return (
    prevProps.audio?.id === nextProps.audio?.id &&
    prevProps.disabled === nextProps.disabled &&
    prevProps.compact === nextProps.compact &&
    prevProps.showTitle === nextProps.showTitle &&
    prevProps.showProgress === nextProps.showProgress
  );
};

export const MemoizedAudioPlayerAdapter = memo(AudioPlayerAdapter, arePropsEqual);
export { MemoizedAudioPlayerAdapter as AudioPlayerAdapter };
export default MemoizedAudioPlayerAdapter;