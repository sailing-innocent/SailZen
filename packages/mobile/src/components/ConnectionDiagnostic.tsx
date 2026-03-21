import React, { useState, useEffect } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Card, Text, Button, useTheme, ActivityIndicator } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { apiClient } from '../api/client';
import { syncService, type SyncResult } from '../services/syncService';
import { useNetworkStatus } from '../hooks/useNetwork';

export function ConnectionDiagnostic() {
  const theme = useTheme();
  const { isConnected, connectionType } = useNetworkStatus();
  const [isTesting, setIsTesting] = useState(false);
  const [testResults, setTestResults] = useState<{
    apiReachable: boolean | null;
    syncResult: SyncResult | null;
    error: string | null;
  }>({
    apiReachable: null,
    syncResult: null,
    error: null,
  });

  const runDiagnostics = async () => {
    setIsTesting(true);
    setTestResults({
      apiReachable: null,
      syncResult: null,
      error: null,
    });

    try {
      // Test 1: Check API connection
      console.log('[Diagnostic] Testing API connection...');
      const apiReachable = await apiClient.healthCheck();
      setTestResults((prev) => ({ ...prev, apiReachable }));

      if (apiReachable) {
        // Test 2: Try to sync
        console.log('[Diagnostic] Testing data sync...');
        const syncResult = await syncService.syncAll();
        setTestResults((prev) => ({ ...prev, syncResult }));
      }
    } catch (error) {
      setTestResults((prev) => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Unknown error',
      }));
    } finally {
      setIsTesting(false);
    }
  };

  useEffect(() => {
    runDiagnostics();
  }, []);

  return (
    <ScrollView style={styles.container}>
      <Card style={styles.card}>
        <Card.Title
          title="连接诊断"
          subtitle="检查与后端服务器的连接状态"
          left={(props) => <MaterialCommunityIcons {...props} name="connection" size={24} />}
        />
        <Card.Content>
          {/* Network Status */}
          <View style={styles.statusRow}>
            <MaterialCommunityIcons
              name={isConnected ? 'wifi' : 'wifi-off'}
              size={24}
              color={isConnected ? '#4CAF50' : '#F44336'}
            />
            <View style={styles.statusText}>
              <Text variant="bodyLarge">
                {isConnected ? '网络已连接' : '网络未连接'}
              </Text>
              {isConnected && connectionType && (
                <Text variant="bodySmall" style={{ color: '#757575' }}>
                  连接类型: {connectionType}
                </Text>
              )}
            </View>
          </View>

          {/* API Connection */}
          <View style={styles.statusRow}>
            {testResults.apiReachable === null ? (
              <ActivityIndicator size="small" />
            ) : (
              <MaterialCommunityIcons
                name={testResults.apiReachable ? 'check-circle' : 'close-circle'}
                size={24}
                color={testResults.apiReachable ? '#4CAF50' : '#F44336'}
              />
            )}
            <View style={styles.statusText}>
              <Text variant="bodyLarge">
                {testResults.apiReachable === null
                  ? '正在检查 API...'
                  : testResults.apiReachable
                  ? 'API 可访问'
                  : 'API 无法访问'}
              </Text>
            </View>
          </View>

          {/* Sync Results */}
          {testResults.syncResult && (
            <View style={styles.syncResults}>
              <Text variant="titleSmall" style={styles.sectionTitle}>
                同步结果
              </Text>
              
              <View style={styles.statsGrid}>
                <StatCard
                  icon="upload"
                  label="已上传"
                  value={>
                    testResults.syncResult.uploaded.weights +
                    testResults.syncResult.uploaded.exercises +
                    testResults.syncResult.uploaded.plans
                  }
                  color={theme.colors.primary}
                />
                <StatCard
                  icon="download"
                  label="已下载"
                  value={>
                    testResults.syncResult.downloaded.weights +
                    testResults.syncResult.downloaded.exercises +
                    testResults.syncResult.downloaded.plans
                  }
                  color="#2196F3"
                />
              </View>

              {testResults.syncResult.errors.length > 0 && (
                <View style={styles.errorsContainer}>
                  <Text variant="bodySmall" style={{ color: '#F44336' }}>
                    错误: {testResults.syncResult.errors.length} 个
                  </Text>
                </View>
              )}
            </View>
          )}

          {/* Error Display */}
          {testResults.error && (
            <View style={styles.errorContainer}>
              <MaterialCommunityIcons name="alert-circle" size={24} color="#F44336" />
              <Text variant="bodyMedium" style={styles.errorText}>
                {testResults.error}
              </Text>
            </View>
          )}
        </Card.Content>
        
        <Card.Actions>
          <Button
            mode="contained"
            onPress={runDiagnostics}
            loading={isTesting}
            disabled={isTesting}
            icon="refresh"
          >
            重新测试
          </Button>
        </Card.Actions>
      </Card>

      {/* Configuration Info */}
      <Card style={styles.card}>
        <Card.Title
          title="配置信息"
          subtitle="当前 API 配置"
        />
        <Card.Content>
          <Text variant="bodySmall" style={styles.configText}>
            API Base URL:
          </Text>
          <Text variant="bodyMedium" selectable>
            {process.env.API_BASE_URL || 'http://10.0.2.2:4399/api/v1'}
          </Text>
          
          <Text variant="bodySmall" style={[styles.configText, { marginTop: 8 }]}>
            环境:
          </Text>
          <Text variant="bodyMedium">
            {__DEV__ ? 'Development' : 'Production'}
          </Text>
        </Card.Content>
      </Card>
    </ScrollView>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: string;
  label: string;
  value: number;
  color: string;
}) {
  return (
    <View style={[styles.statCard, { backgroundColor: color + '15' }]} key={label}>
      <MaterialCommunityIcons name={icon} size={24} color={color} />
      <Text variant="titleLarge" style={[styles.statValue, { color }]} numberOfLines={1}>
        {value}
      </Text>
      <Text variant="bodySmall" style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  card: {
    marginBottom: 16,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  statusText: {
    marginLeft: 12,
    flex: 1,
  },
  syncResults: {
    marginTop: 16,
  },
  sectionTitle: {
    marginBottom: 12,
    fontWeight: '600',
  },
  statsGrid: {
    flexDirection: 'row',
    gap: 12,
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    padding: 16,
    borderRadius: 12,
  },
  statValue: {
    fontWeight: 'bold',
    marginTop: 8,
  },
  statLabel: {
    marginTop: 4,
    color: '#757575',
  },
  errorsContainer: {
    marginTop: 12,
    padding: 12,
    backgroundColor: '#FFEBEE',
    borderRadius: 8,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
    padding: 12,
    backgroundColor: '#FFEBEE',
    borderRadius: 8,
  },
  errorText: {
    marginLeft: 12,
    color: '#F44336',
    flex: 1,
  },
  configText: {
    color: '#757575',
    marginBottom: 4,
  },
});
