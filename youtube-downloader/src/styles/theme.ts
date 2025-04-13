
export const theme = {
  colors: {
    primary: '#3498db',
    secondary: '#007bff',
    tertiary: '#28a745',
    error: '#dc3545',
    warning: '#ffc107',
    info: '#17a2b8',
    border: '#ddd',
    backgroundLight: '#f8f8f8',
    textDark: '#666',
    tabActiveBg: '#e3f2fd',
    tabHoverBg: '#f0f8ff',
    white: '#ffffff',
    black: '#000000',
    
    // Cores para temas (inspiradas no projeto de referência)
    dark: {
      primary: '#0f172a',
      secondary: '#1e293b',
      text: '#f8fafc',
      textSecondary: '#94a3b8',
      border: '#334155',
      accent: '#38BDF8',
      accentLight: '#93c5fd',
    },
    light: {
      primary: '#f8fafc',
      secondary: '#f1f5f9',
      text: '#0f172a',
      textSecondary: '#334155',
      border: '#cbd5e1',
      accent: '#0284c7',
      accentLight: '#3b82f6',
    }
  },
  
  typography: {
    fontFamily: {
      regular: 'Inter-Regular',
      medium: 'Inter-Medium',
      semiBold: 'Inter-SemiBold',
      bold: 'Inter-Bold',
      mono: 'JetBrainsMono-Regular'
    },
    fontSize: {
      xs: 12,
      sm: 14,
      md: 16,
      lg: 18,
      xl: 20,
      '2xl': 24,
      '3xl': 30,
      '4xl': 36
    }
  },
  
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    '2xl': 48,
    '3xl': 64
  },
  
  borderRadius: {
    sm: 4,
    md: 8,
    lg: 12,
    xl: 16,
    '2xl': 24,
    full: 9999
  },
  
  shadows: {
    sm: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.18,
      shadowRadius: 1.0,
      elevation: 1
    },
    md: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.23,
      shadowRadius: 2.62,
      elevation: 4
    },
    lg: {
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.30,
      shadowRadius: 4.65,
      elevation: 8
    }
  }
};
