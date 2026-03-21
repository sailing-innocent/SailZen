import React, { useEffect, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { PaperProvider, ActivityIndicator, Text } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Slot } from 'expo-router';
import { View, StyleSheet } from 'react-native';
import { theme } from '../theme';
import { useMigrations } from '../hooks/useDatabase';
import { syncService } from '../services/syncService';
import { useSyncStore } from '../stores/syncStore';

function DatabaseInitializer({ children }: { children: React.ReactNode }) {
  const { isReady, isMigrating, error } = useMigrations();
  const { setPendingCount } = useSyncStore();

  useEffect(() => {
    if (isReady) {
      // Initialize pending count on startup
      syncService.getPendingCount().then((count) => {
        setPendingCount(count);
      });
    }
  }, [isReady, setPendingCount]);

  if (isMigrating) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={theme.colors.primary} />
        <Text style={styles.loadingText}>正在初始化数据库...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>数据库初始化失败</Text>
        <Text style={styles.errorDetail}>{error}</Text>
      </View>
    );
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <StatusBar style="auto" />
        <DatabaseInitializer>
          <Slot />
        </DatabaseInitializer>
      </PaperProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#757575',
  },
  errorText: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#F44336',
  },
  errorDetail: {
    marginTop: 8,
    fontSize: 14,
    color: '#757575',
  },
});
