
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { ThemeProvider } from './src/context/ThemeContext';
import { AuthProvider } from './src/context/AuthContext';
import { DownloadProvider } from './src/context/DownloadContext';
import { AudioPlayerProvider } from './src/context/AudioPlayerContext';
import Navigation from './src/navigation';

// Componente principal App
export default function App() {
  return (
    <SafeAreaProvider>
      <ThemeProvider>
        <AuthProvider>
          <DownloadProvider>
            <AudioPlayerProvider>
              <StatusBar style="auto" />
              <Navigation />
            </AudioPlayerProvider>
          </DownloadProvider>
        </AuthProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
