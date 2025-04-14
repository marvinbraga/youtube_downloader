
import { Dimensions } from 'react-native';

const { width, height } = Dimensions.get('window');

// Definições dos temas
const darkTheme = {
  // Cores principais
  primary: '#4F46E5',
  secondary: '#3B82F6',
  accent: '#38BDF8',
  accentLight: '#93c5fd',
  
  // Cores de background
  background: {
    primary: '#0f172a',
    secondary: '#1e293b',
  },
  
  // Cores de texto
  text: {
    primary: '#f8fafc',
    secondary: '#94a3b8',
  },
  
  // Cores de bordas
  border: '#334155',
  
  // Cores de status
  success: '#22c55e',
  warning: '#f59e0b',
  error: '#ef4444',
  info: '#38BDF8',
  tertiary: '#22c55e', // Adicionando tertiary que é usado no código
  
  // Cores de background para componentes específicos
  backgroundLight: '#1e293b', // Adicionando cores que são usadas diretamente
  textDark: '#f8fafc',
  tabActiveBg: 'rgba(59, 130, 246, 0.2)',
};

const lightTheme = {
  // Cores principais
  primary: '#3b82f6',
  secondary: '#60a5fa',
  accent: '#0284c7',
  accentLight: '#3b82f6',
  
  // Cores de background
  background: {
    primary: '#f8fafc',
    secondary: '#f1f5f9',
  },
  
  // Cores de texto
  text: {
    primary: '#0f172a',
    secondary: '#334155',
  },
  
  // Cores de bordas
  border: '#cbd5e1',
  
  // Cores de status
  success: '#22c55e',
  warning: '#f59e0b',
  error: '#ef4444',
  info: '#38BDF8',
  tertiary: '#22c55e', // Adicionando tertiary que é usado no código
  
  // Cores de background para componentes específicos
  backgroundLight: '#f1f5f9', // Adicionando cores que são usadas diretamente
  textDark: '#0f172a',
  tabActiveBg: 'rgba(59, 130, 246, 0.1)',
};

// Gradientes para uso com LinearGradient
const gradients = {
  primary: {
    dark: ['#4F46E5', '#3B82F6'],
    light: ['#3b82f6', '#60a5fa'],
  },
  secondary: {
    dark: ['#3B82F6', '#38BDF8'],
    light: ['#60a5fa', '#7dd3fc'],
  },
  background: {
    dark: ['#1E293B', '#0F172A'],
    light: ['#f1f5f9', '#e2e8f0'],
  },
};

// Sombras para diferentes elevações
const shadows = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.18,
    shadowRadius: 1.0,
    elevation: 1,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 3,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.30,
    shadowRadius: 4.65,
    elevation: 8,
  },
  xl: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 5 },
    shadowOpacity: 0.34,
    shadowRadius: 6.27,
    elevation: 10,
  },
};

// Tamanhos de fontes
const fontSizes = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 18,
  xl: 20,
  '2xl': 24,
  '3xl': 30,
  '4xl': 36,
};

// Fontes (para usar com expo-font)
const fonts = {
  regular: 'Inter-Regular',
  medium: 'Inter-Medium',
  semiBold: 'Inter-SemiBold',
  bold: 'Inter-Bold',
  mono: 'JetBrainsMono-Regular',
};

// Espaçamentos
const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  '2xl': 48,
  '3xl': 64,
};

// Raios de borda
const borderRadius = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  '2xl': 24,
  full: 9999,
};

// Animações (para usar com Animated)
const animations = {
  timing: {
    fast: 200,
    normal: 300,
    slow: 500,
  },
};

// Estilos de componentes específicos
const componentStyles = {
  // Estilos de cartão
  card: {
    padding: spacing.md,
    borderRadius: borderRadius.xl,
    borderWidth: 1,
  },
  
  // Estilos de botão
  button: {
    primary: {
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      borderRadius: borderRadius.md,
    },
    secondary: {
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      borderRadius: borderRadius.md,
      borderWidth: 1,
    },
  },
  
  // Estilos para itens de lista
  listItem: {
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderRadius: borderRadius.lg,
    borderLeftWidth: 4,
  },
  
  // Estilos de input
  input: {
    height: 48,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderRadius: borderRadius.md,
  },
  
  // Estilos de modal
  modal: {
    overlay: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
    },
    container: {
      width: width * 0.85,
      maxHeight: height * 0.7,
      borderRadius: borderRadius.xl,
      padding: spacing.md,
    },
    header: {
      paddingBottom: spacing.sm,
      borderBottomWidth: 1,
    },
    body: {
      paddingVertical: spacing.md,
    },
    footer: {
      paddingTop: spacing.sm,
      borderTopWidth: 1,
    },
  },
  
  // Estilos de abas
  tab: {
    container: {
      flexDirection: 'row',
      marginBottom: spacing.md,
    },
    item: {
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      borderRadius: borderRadius.sm,
    },
  },
  
  // Estilo de mensagem de status
  statusMessage: {
    container: {
      padding: spacing.md,
      borderRadius: borderRadius.lg,
      marginVertical: spacing.sm,
    },
    text: {
      fontSize: fontSizes.md,
    },
    icon: {
      marginRight: spacing.sm,
    },
  },
};

// Estados de elementos visuais
const states = {
  // Estados para elementos de item
  item: {
    active: {
      borderLeftColor: darkTheme.accent,
      backgroundColor: 'rgba(59, 130, 246, 0.2)',
    },
    highlighted: {
      backgroundColor: 'rgba(255, 215, 0, 0.3)',
      borderLeftColor: 'goldenrod',
    },
    disabled: {
      opacity: 0.5,
    },
  },
  
  // Estados de botão
  button: {
    disabled: {
      opacity: 0.6,
    },
    pressed: {
      opacity: 0.8,
    },
  },
};

// Propriedades comuns a ambos os temas
const commonTheme = {
  gradients,
  shadows,
  fontSizes,
  fonts,
  spacing,
  borderRadius,
  animations,
  componentStyles,
  states,
  screen: {
    width,
    height,
    isSmall: width < 375,
    isMedium: width >= 375 && width < 768,
    isLarge: width >= 768,
  },
};

// Exportando ambos os temas
export const themes = {
  light: {
    colors: {
      ...lightTheme,
    },
    ...commonTheme,
  },
  dark: {
    colors: {
      ...darkTheme,
    },
    ...commonTheme,
  }
};

// Exportação padrão - facilita o uso
export default themes;
