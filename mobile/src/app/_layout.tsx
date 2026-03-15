import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Slot } from 'expo-router';
import { theme } from './theme';

export default function App() {
  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <StatusBar style="auto" />
        <Slot />
      </PaperProvider>
    </SafeAreaProvider>
  );
}
