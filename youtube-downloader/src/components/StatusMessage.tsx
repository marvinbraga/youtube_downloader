
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { theme } from '../styles/theme';

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
  
  useEffect(() => {
    Animated.sequence([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.delay(duration - 600),
      Animated.timing(fadeAnim, {
        toValue: 0,
        duration: 300,
        useNativeDriver: true,
      })
    ]).start(() => {
      if (onClose) onClose();
    });
  }, [fadeAnim, duration, onClose]);
  
  const getBackgroundColor = () => {
    switch (type) {
      case 'error':
        return theme.colors.error;
      case 'success':
        return theme.colors.tertiary;
      case 'info':
        return theme.colors.info;
      default:
        return theme.colors.info;
    }
  };
  
  return (
    <Animated.View 
      style={[
        styles.container, 
        { backgroundColor: getBackgroundColor(), opacity: fadeAnim }
      ]}
    >
      <Text style={styles.message}>{message}</Text>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 40,
    right: 20,
    left: 20,
    padding: 12,
    borderRadius: 8,
    zIndex: 1000,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
  },
  message: {
    color: 'white',
    fontWeight: '500',
    textAlign: 'center',
  }
});

export default StatusMessage;
