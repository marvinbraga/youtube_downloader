
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
  const { isDarkTheme, colors } = useTheme();
  
  // Determinar os gradientes com base no tema e variante
  const getGradientColors = () => {
    if (gradientColors && gradientColors.length >= 2) {
      return gradientColors;
    }
    
    // Gradientes padrão para cada variante
    switch (variant) {
      case 'primary':
        return ['#4F46E5', '#3B82F6'];
      case 'secondary':
        return ['#3B82F6', '#38BDF8'];
      case 'success':
        return ['#22c55e', '#4ade80'];
      case 'warning':
        return ['#f59e0b', '#fbbf24'];
      case 'danger':
        return ['#ef4444', '#f87171'];
      default:
        return ['#4F46E5', '#3B82F6'];
    }
  };
  
  // Obter tamanho baseado na opção
  const getSize = () => {
    switch (size) {
      case 'sm':
        return {
          paddingVertical: 6,
          paddingHorizontal: 12,
          fontSize: 14,
          iconSize: 14,
        };
      case 'lg':
        return {
          paddingVertical: 12,
          paddingHorizontal: 24,
          fontSize: 18,
          iconSize: 18,
        };
      case 'md':
      default:
        return {
          paddingVertical: 10,
          paddingHorizontal: 16,
          fontSize: 16,
          iconSize: 16,
        };
    }
  };
  
  const sizeStyle = getSize();
  
  // Conteúdo do botão (ícones, texto ou loading)
  const renderContent = () => {
    const content = (
      <>
        {isLoading ? (
          <ActivityIndicator color="#fff" size={sizeStyle.iconSize} />
        ) : (
          <>
            {leftIcon && (
              <Feather 
                name={leftIcon as any} 
                size={sizeStyle.iconSize} 
                color="#fff" 
                style={styles.leftIcon} 
              />
            )}
            <Text style={[
              styles.text, 
              { fontSize: sizeStyle.fontSize },
              textStyle
            ]}>
              {title}
            </Text>
            {rightIcon && (
              <Feather 
                name={rightIcon as any} 
                size={sizeStyle.iconSize} 
                color="#fff" 
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
            },
            disabled && styles.disabled,
            style
          ]}
        >
          {content}
        </LinearGradient>
      );
    }
    
    // Para botões 'outline' e 'secondary'
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
          },
          disabled && styles.disabled,
          style
        ]}
        disabled={disabled || isLoading}
        {...rest}
      >
        {content}
      </TouchableOpacity>
    );
  };
  
  return renderContent();
};

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 8,
    overflow: 'hidden',
  },
  text: {
    color: 'white',
    fontWeight: '600',
    textAlign: 'center',
  },
  leftIcon: {
    marginRight: 8,
  },
  rightIcon: {
    marginLeft: 8,
  },
  disabled: {
    opacity: 0.6,
  },
});

export default Button;
