
import React from 'react';
import { 
  TouchableOpacity, 
  Text, 
  StyleSheet, 
  ActivityIndicator,
  StyleProp,
  ViewStyle,
  TextStyle,
  TouchableOpacityProps
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useTheme } from '../context/ThemeContext';

interface ButtonProps extends TouchableOpacityProps {
  title: string;
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'success' | 'warning';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: string;
  rightIcon?: string;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  gradientColors?: string[];
}

const Button: React.FC<ButtonProps> = ({
  title,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  style,
  textStyle,
  gradientColors,
  disabled,
  ...rest
}) => {
  const { isDarkTheme, colors, theme } = useTheme();
  
  // Determinar os gradientes com base no tema e variante
  const getGradientColors = () => {
    if (gradientColors && gradientColors.length >= 2) {
      return gradientColors;
    }
    
    // Gradientes padrão baseados no tema atual
    const themeMode = isDarkTheme ? 'dark' : 'light';
    
    // Gradientes padrão para cada variante
    switch (variant) {
      case 'primary':
        return theme.gradients.primary[themeMode];
      case 'secondary':
        return theme.gradients.secondary[themeMode];
      case 'success':
        return [colors.success, isDarkTheme ? '#4ade80' : '#86efac'];
      case 'warning':
        return [colors.warning, isDarkTheme ? '#fbbf24' : '#fcd34d'];
      case 'danger':
        return [colors.error, isDarkTheme ? '#f87171' : '#fca5a5'];
      default:
        return theme.gradients.primary[themeMode];
    }
  };
  
  // Obter tamanho baseado na opção
  const getSize = () => {
    switch (size) {
      case 'sm':
        return {
          paddingVertical: theme.spacing.xs,
          paddingHorizontal: theme.spacing.sm,
          fontSize: theme.fontSizes.sm,
          iconSize: 14,
        };
      case 'lg':
        return {
          paddingVertical: theme.spacing.sm,
          paddingHorizontal: theme.spacing.md,
          fontSize: theme.fontSizes.lg,
          iconSize: 18,
        };
      case 'md':
      default:
        return {
          paddingVertical: theme.spacing.sm,
          paddingHorizontal: theme.spacing.md,
          fontSize: theme.fontSizes.md,
          iconSize: 16,
        };
    }
  };
  
  const sizeStyle = getSize();
  
  // Conteúdo do botão (ícones, texto ou loading)
  const renderContent = () => {
    const iconColor = variant === 'outline' ? colors.text.primary : '#fff';
    const textColor = variant === 'outline' ? colors.text.primary : '#fff';
    
    const content = (
      <>
        {isLoading ? (
          <ActivityIndicator color={textColor} size={sizeStyle.iconSize} />
        ) : (
          <>
            {leftIcon && (
              <Feather 
                name={leftIcon as any} 
                size={sizeStyle.iconSize} 
                color={iconColor} 
                style={styles.leftIcon} 
              />
            )}
            <Text style={[
              styles.text, 
              { fontSize: sizeStyle.fontSize, color: textColor },
              textStyle
            ]}>
              {title}
            </Text>
            {rightIcon && (
              <Feather 
                name={rightIcon as any} 
                size={sizeStyle.iconSize} 
                color={iconColor} 
                style={styles.rightIcon} 
              />
            )}
          </>
        )}
      </>
    );
    
    // Use gradiente para botões 'primary', 'success', 'warning', 'danger'
    if (variant !== 'outline' && variant !== 'secondary') {
      return (
        <LinearGradient
          colors={getGradientColors()}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={[
            styles.button,
            { 
              paddingVertical: sizeStyle.paddingVertical,
              paddingHorizontal: sizeStyle.paddingHorizontal,
              borderRadius: theme.borderRadius.md,
            },
            disabled && theme.states.button.disabled,
            style
          ]}
        >
          {content}
        </LinearGradient>
      );
    }
    
    // Para botões 'outline' e 'secondary'
    return content;
  };
  
  // Se for outline ou secondary, coloca o TouchableOpacity fora
  if (variant === 'outline' || variant === 'secondary') {
    return (
      <TouchableOpacity
        style={[
          styles.button,
          { 
            paddingVertical: sizeStyle.paddingVertical,
            paddingHorizontal: sizeStyle.paddingHorizontal,
            backgroundColor: variant === 'secondary' ? colors.background.secondary : 'transparent',
            borderWidth: variant === 'outline' ? 1 : 0,
            borderColor: colors.border,
            borderRadius: theme.borderRadius.md,
          },
          disabled && theme.states.button.disabled,
          style
        ]}
        disabled={disabled || isLoading}
        {...rest}
      >
        {renderContent()}
      </TouchableOpacity>
    );
  }
  
  // Para botões com gradiente
  return (
    <TouchableOpacity
      activeOpacity={0.8}
      disabled={disabled || isLoading}
      style={[disabled && theme.states.button.disabled]}
      {...rest}
    >
      {renderContent()}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  text: {
    fontWeight: '600',
    textAlign: 'center',
  },
  leftIcon: {
    marginRight: 8,
  },
  rightIcon: {
    marginLeft: 8,
  },
});

export default Button;
