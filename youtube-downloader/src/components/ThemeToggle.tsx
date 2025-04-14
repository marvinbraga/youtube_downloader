
import React from 'react';
import { View, TouchableOpacity, StyleSheet, Text } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';

interface ThemeToggleProps {
  showLabel?: boolean;
}

const ThemeToggle: React.FC<ThemeToggleProps> = ({ showLabel = false }) => {
  const { isDarkTheme, toggleTheme, colors } = useTheme();

  return (
    <View style={styles.container}>
      {showLabel && (
        <Text style={[styles.label, { color: colors.text.primary }]}>
          {isDarkTheme ? 'Modo Escuro' : 'Modo Claro'}
        </Text>
      )}
      
      <TouchableOpacity
        onPress={toggleTheme}
        style={[
          styles.toggle,
          { backgroundColor: isDarkTheme ? colors.background.secondary : '#e2e8f0' }
        ]}
        activeOpacity={0.7}
      >
        <View
          style={[
            styles.indicator,
            { 
              backgroundColor: isDarkTheme ? colors.secondary : colors.accent,
              transform: [{ translateX: isDarkTheme ? 24 : 0 }]
            }
          ]}
        >
          <Feather
            name={isDarkTheme ? 'moon' : 'sun'}
            size={16}
            color="#fff"
          />
        </View>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 16,
  },
  label: {
    marginRight: 8,
    fontSize: 14,
    fontWeight: '500',
  },
  toggle: {
    width: 56,
    height: 30,
    borderRadius: 15,
    padding: 2,
    justifyContent: 'center',
  },
  indicator: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },
});

export default ThemeToggle;
