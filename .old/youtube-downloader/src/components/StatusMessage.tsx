
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { useTheme } from '../context/ThemeContext';

type MessageType = 'error' | 'success' | 'info';

interface StatusMessageProps {
  message: string;
  type: MessageType;
  duration?: number;
  onClose?: () => void;
}

const StatusMessage: React.FC<StatusMessageProps> = ({
  message,
  type,
  duration = 5000,
  onClose
}) => {
  const [fadeAnim] = useState(new Animated.Value(0));
  const { colors, theme } = useTheme();
  
  useEffect(() => {
    Animated.sequence([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: false,
      }),
      Animated.delay(duration - 600),
      Animated.timing(fadeAnim, {
        toValue: 0,
        duration: 300,
        useNativeDriver: false,
      })
    ]).start(() => {
      if (onClose) onClose();
    });
  }, [fadeAnim, duration, onClose]);
  
  const getBackgroundColor = () => {
    switch (type) {
      case 'error':
        return colors.error;
      case 'success':
        return colors.success;
      case 'info':
        return colors.info;
      default:
        return colors.info;
    }
  };
  
  return (
    <Animated.View 
      style={[
        styles.container, 
        theme.componentStyles.statusMessage.container,
        { backgroundColor: getBackgroundColor(), opacity: fadeAnim },
        theme.shadows.md
      ]}
    >
      <Text style={[
        styles.message, 
        theme.componentStyles.statusMessage.text
      ]}>
        {message}
      </Text>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 40,
    right: 20,
    left: 20,
    zIndex: 1000,
  },
  message: {
    color: 'white',
    fontWeight: '500',
    textAlign: 'center',
  }
});

export default StatusMessage;
