
import React from 'react';
import { NavigationContainer, DefaultTheme, DarkTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { VideosScreen, AudioScreen, DownloadScreen } from '../screens';
import { useTheme } from '../context/ThemeContext';
import ThemeToggle from '../components/ThemeToggle';

const Tab = createBottomTabNavigator();

const Navigation = () => {
  const { isDarkTheme, colors, theme } = useTheme();
  
  // Criar um tema personalizado para o NavigationContainer baseado no tema atual
  const navigationTheme = {
    ...(isDarkTheme ? DarkTheme : DefaultTheme),
    colors: {
      ...(isDarkTheme ? DarkTheme.colors : DefaultTheme.colors),
      primary: colors.primary,
      background: colors.background.primary,
      card: colors.background.secondary,
      text: colors.text.primary,
      border: colors.border,
    },
  };
  
  return (
    <NavigationContainer theme={navigationTheme}>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ focused, color, size }) => {
            let iconName;

            if (route.name === 'Vídeos') {
              iconName = focused ? 'videocam' : 'videocam-outline';
            } else if (route.name === 'Áudio') {
              iconName = focused ? 'headset' : 'headset-outline';
            } else if (route.name === 'Download') {
              iconName = focused ? 'download' : 'download-outline';
            }

            return <Ionicons name={iconName as any} size={size} color={color} />;
          },
          tabBarActiveTintColor: colors.accent,
          tabBarInactiveTintColor: colors.text.secondary,
          tabBarStyle: {
            backgroundColor: colors.background.secondary,
            borderTopColor: colors.border,
          },
          headerStyle: {
            backgroundColor: colors.background.secondary,
            shadowColor: colors.accent,
            shadowOpacity: 0.1,
            shadowOffset: { width: 0, height: 2 },
            shadowRadius: 2,
            elevation: 3,
          },
          headerTintColor: colors.text.primary,
          headerTitleStyle: {
            fontWeight: 'bold',
          },
          headerRight: () => (
            <ThemeToggle showLabel={false} />
          ),
        })}
      >
        <Tab.Screen 
          name="Vídeos" 
          component={VideosScreen} 
          options={{
            headerRight: () => (
              <ThemeToggle showLabel={false} />
            ),
          }}
        />
        <Tab.Screen 
          name="Áudio" 
          component={AudioScreen}
          options={{
            headerRight: () => (
              <ThemeToggle showLabel={false} />
            ),
          }}
        />
        <Tab.Screen 
          name="Download" 
          component={DownloadScreen}
          options={{
            headerRight: () => (
              <ThemeToggle showLabel={false} />
            ),
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
};

export default Navigation;
