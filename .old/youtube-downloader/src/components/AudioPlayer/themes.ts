import { Dimensions, Platform } from 'react-native';

const { width: screenWidth } = Dimensions.get('window');

// Detectar tamanho da tela
const isSmallScreen = screenWidth < 375;
const isMediumScreen = screenWidth >= 375 && screenWidth < 768;
const isLargeScreen = screenWidth >= 768;

// Cores específicas para o player
export const playerTheme = {
  light: {
    // Cores principais
    primary: '#3b82f6',
    primaryHover: '#2563eb',
    primaryActive: '#1d4ed8',
    
    // Superfícies
    surface: '#ffffff',
    surfaceHover: '#f9fafb',
    surfaceActive: '#f3f4f6',
    
    // Textos
    textPrimary: '#1f2937',
    textSecondary: '#6b7280',
    textTertiary: '#9ca3af',
    
    // Controles
    controlBackground: '#f3f4f6',
    controlBorder: '#e5e7eb',
    controlIcon: '#374151',
    controlIconHover: '#1f2937',
    
    // Progress Bar
    progressBackground: '#e5e7eb',
    progressBuffered: '#d1d5db',
    progressFill: '#3b82f6',
    progressHandle: '#3b82f6',
    progressHandleBorder: '#ffffff',
    
    // Estados
    loadingColor: '#6b7280',
    errorBackground: '#fee2e2',
    errorText: '#dc2626',
    successBackground: '#dcfce7',
    successText: '#16a34a',
    
    // Sombras
    shadowLight: 'rgba(0, 0, 0, 0.05)',
    shadowMedium: 'rgba(0, 0, 0, 0.1)',
    shadowDark: 'rgba(0, 0, 0, 0.15)',
    
    // Overlays
    tooltipBackground: '#1f2937',
    tooltipText: '#ffffff',
  },
  
  dark: {
    // Cores principais
    primary: '#60a5fa',
    primaryHover: '#93c5fd',
    primaryActive: '#3b82f6',
    
    // Superfícies
    surface: '#1e293b',
    surfaceHover: '#334155',
    surfaceActive: '#475569',
    
    // Textos
    textPrimary: '#f1f5f9',
    textSecondary: '#cbd5e1',
    textTertiary: '#94a3b8',
    
    // Controles
    controlBackground: '#334155',
    controlBorder: '#475569',
    controlIcon: '#e2e8f0',
    controlIconHover: '#f8fafc',
    
    // Progress Bar
    progressBackground: '#334155',
    progressBuffered: '#475569',
    progressFill: '#60a5fa',
    progressHandle: '#60a5fa',
    progressHandleBorder: '#1e293b',
    
    // Estados
    loadingColor: '#94a3b8',
    errorBackground: '#7f1d1d',
    errorText: '#fca5a5',
    successBackground: '#14532d',
    successText: '#86efac',
    
    // Sombras
    shadowLight: 'rgba(0, 0, 0, 0.2)',
    shadowMedium: 'rgba(0, 0, 0, 0.3)',
    shadowDark: 'rgba(0, 0, 0, 0.4)',
    
    // Overlays
    tooltipBackground: '#f1f5f9',
    tooltipText: '#1e293b',
  }
};

// Tamanhos responsivos
export const sizes = {
  mobile: {
    playerHeight: 120,
    controlButtonSize: 36,
    stopButtonSize: 32,
    iconSize: 20,
    fontSize: 12,
    timeFontSize: 11,
    padding: 12,
    borderRadius: 8,
    progressBarHeight: 4,
  },
  tablet: {
    playerHeight: 140,
    controlButtonSize: 44,
    stopButtonSize: 36,
    iconSize: 24,
    fontSize: 14,
    timeFontSize: 13,
    padding: 14,
    borderRadius: 10,
    progressBarHeight: 5,
  },
  desktop: {
    playerHeight: 160,
    controlButtonSize: 48,
    stopButtonSize: 40,
    iconSize: 28,
    fontSize: 16,
    timeFontSize: 14,
    padding: 16,
    borderRadius: 12,
    progressBarHeight: 6,
  }
};

// Obter tamanhos baseado na plataforma e largura da tela
export const getResponsiveSizes = () => {
  if (Platform.OS === 'web') {
    if (isLargeScreen) return sizes.desktop;
    if (isMediumScreen) return sizes.tablet;
    return sizes.mobile;
  }
  
  // Mobile/Tablet nativo
  if (isSmallScreen) return sizes.mobile;
  if (isMediumScreen) return sizes.tablet;
  return sizes.desktop;
};

// Animações e transições
export const animations = {
  fast: 150,
  normal: 250,
  slow: 350,
  
  // Curvas de animação
  easing: {
    smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
    bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    sharp: 'cubic-bezier(0.4, 0, 0.6, 1)',
  }
};

// Gradientes para estados especiais
export const gradients = {
  light: {
    playButton: ['#3b82f6', '#2563eb'],
    progressBar: ['#60a5fa', '#3b82f6'],
    loading: ['#e5e7eb', '#d1d5db'],
  },
  dark: {
    playButton: ['#60a5fa', '#3b82f6'],
    progressBar: ['#93c5fd', '#60a5fa'],
    loading: ['#475569', '#334155'],
  }
};

// Ícones customizados (podem ser substituídos por SVGs)
export const iconNames = {
  play: 'play',
  pause: 'pause',
  stop: 'stop',
  volumeLow: 'volume-1',
  volumeHigh: 'volume-2',
  volumeMute: 'volume-x',
  download: 'download',
  share: 'share-2',
  playlist: 'list',
  repeat: 'repeat',
  shuffle: 'shuffle',
  skipBack: 'skip-back',
  skipForward: 'skip-forward',
  settings: 'settings',
  minimize: 'minimize-2',
  maximize: 'maximize-2',
};

// Função helper para obter o tema correto
export const getPlayerTheme = (isDarkMode: boolean) => {
  return isDarkMode ? playerTheme.dark : playerTheme.light;
};

// Função helper para obter gradientes
export const getGradients = (isDarkMode: boolean) => {
  return isDarkMode ? gradients.dark : gradients.light;
};

// Estilos de acessibilidade
export const accessibility = {
  // Tamanhos mínimos para toque
  minTouchSize: 44,
  
  // Labels ARIA
  labels: {
    playButton: 'Reproduzir áudio',
    pauseButton: 'Pausar áudio',
    stopButton: 'Parar áudio',
    progressBar: 'Barra de progresso do áudio',
    timeDisplay: 'Tempo de reprodução',
    volumeControl: 'Controle de volume',
  },
  
  // Roles ARIA
  roles: {
    player: 'region',
    controls: 'group',
    progressBar: 'slider',
    button: 'button',
  }
};

// Media queries para web
export const mediaQueries = {
  mobile: '@media (max-width: 640px)',
  tablet: '@media (min-width: 641px) and (max-width: 1024px)',
  desktop: '@media (min-width: 1025px)',
  
  // Orientação
  portrait: '@media (orientation: portrait)',
  landscape: '@media (orientation: landscape)',
  
  // Preferências de usuário
  reducedMotion: '@media (prefers-reduced-motion: reduce)',
  darkMode: '@media (prefers-color-scheme: dark)',
  lightMode: '@media (prefers-color-scheme: light)',
};