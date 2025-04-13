
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { VideosScreen, AudioScreen, DownloadScreen } from '../screens';
import { theme } from '../styles/theme';

const Tab = createBottomTabNavigator();

const Navigation = () => {
  return (
    <NavigationContainer>
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
          tabBarActiveTintColor: theme.colors.primary,
          tabBarInactiveTintColor: 'gray',
          headerStyle: {
            backgroundColor: theme.colors.primary,
          },
          headerTintColor: '#fff',
          headerTitleStyle: {
            fontWeight: 'bold',
          },
        })}
      >
        <Tab.Screen name="Vídeos" component={VideosScreen} />
        <Tab.Screen name="Áudio" component={AudioScreen} />
        <Tab.Screen name="Download" component={DownloadScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
};

export default Navigation;
