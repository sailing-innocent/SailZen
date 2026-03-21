import React, { useEffect, useState, useCallback } from 'react';
import { View, StyleSheet, ScrollView, RefreshControl } from 'react-native';
import {
  Text,
  useTheme,
  Button,
  Portal,
  Dialog,
  TextInput,
  HelperText,
  ProgressBar,
  Card,
  Snackbar,
  List,
} from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useWeightPlan } from '../../hooks/useWeightPlan';
import { useWeights } from '../../hooks/useWeights';
import { useMigrations } from '../../hooks/useDatabase';
import { WeightPlan } from '../../db/schema';
import { format, differenceInDays, isAfter, isValid, parseISO } from 'date-fns';
import DateTimePicker from '@react-native-community/datetimepicker';

export default function PlanScreen() {
  const theme = useTheme();
  const { isReady: isDbReady } = useMigrations();
  const { activePlan, plans, fetchPlans, createPlan, deletePlan, calculateProgress } = useWeightPlan();
  const { weights, fetchWeights, getStatistics } = useWeights();

  const [currentWeight, setCurrentWeight] = useState<number | null>(null);
  const [progress, setProgress] = useState<ReturnType<typeof calculateProgress>>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [snackbarVisible, setSnackbarVisible] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  // Dialog states
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showHistoryDialog, setShowHistoryDialog] = useState(false);

  // Form states
  const [targetWeight, setTargetWeight] = useState('');
  const [targetDate, setTargetDate] = useState(new Date());
  const [startWeight, setStartWeight] = useState('');
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isDbReady) {
      loadData();
    }
  }, [isDbReady]);

  useEffect(() => {
    if (weights.length > 0) {
      setCurrentWeight(weights[0].value);
    }
  }, [weights]);

  useEffect(() => {
    if (activePlan && currentWeight !== null) {
      setProgress(calculateProgress(currentWeight));
    } else {
      setProgress(null);
    }
  }, [activePlan, currentWeight, calculateProgress]);

  const loadData = async () => {
    await fetchPlans();
    await fetchWeights({ limit: 1 });
  };

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, []);

  const validateForm = (): boolean => {
    const target = parseFloat(targetWeight);
    const start = startWeight ? parseFloat(startWeight) : currentWeight;

    if (isNaN(target) || target <= 0 || target > 500) {
      setFormError('请输入有效的目标体重 (0-500 kg)');
      return false;
    }

    if (start && (isNaN(start) || start <= 0 || start > 500)) {
      setFormError('请输入有效的起始体重 (0-500 kg)');
      return false;
    }

    if (!isAfter(targetDate, new Date())) {
      setFormError('目标日期必须是未来日期');
      return false;
    }

    setFormError(null);
    return true;
  };

  const handleCreatePlan = async () => {
    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      await createPlan(
        parseFloat(targetWeight),
        targetDate,
        startWeight ? parseFloat(startWeight) : undefined
      );
      setShowCreateDialog(false);
      setSnackbarMessage('目标已创建');
      setSnackbarVisible(true);
      // Reset form
      setTargetWeight('');
      setStartWeight('');
      setTargetDate(new Date());
    } catch (err) {
      setFormError(err instanceof Error ? err.message : '创建目标失败');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeletePlan = async (id: number) => {
    try {
      await deletePlan(id);
      setSnackbarMessage('目标已删除');
      setSnackbarVisible(true);
    } catch (err) {
      setSnackbarMessage('删除失败: ' + (err instanceof Error ? err.message : '未知错误'));
      setSnackbarVisible(true);
    }
  };

  const onDateChange = (event: any, selectedDate?: Date) => {
    setShowDatePicker(false);
    if (selectedDate) {
      setTargetDate(selectedDate);
    }
  };

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'ahead':
        return '#2196F3';
      case 'on_track':
        return '#4CAF50';
      case 'behind':
        return '#F44336';
      default:
        return theme.colors.primary;
    }
  };

  const getStatusText = (status?: string) => {
    switch (status) {
      case 'ahead':
        return '超前';
      case 'on_track':
        return '正常';
      case 'behind':
        return '落后';
      default:
        return '-';
    }
  };

  if (!isDbReady) {
    return (
      <View style={styles.centered}>
        <Text>正在初始化数据库...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
      >
        {!activePlan ? (
          <Card style={styles.emptyCard}>
            <Card.Content style={styles.emptyContent}>
              <MaterialCommunityIcons name="target" size={64} color="#E0E0E0" />
              <Text variant="titleLarge" style={styles.emptyTitle}>
                还没有体重目标
              </Text>
              <Text variant="bodyMedium" style={styles.emptyText}>
                设置一个目标，开始你的健康之旅
              </Text>
              <Button
                mode="contained"
                onPress={() => setShowCreateDialog(true)}
                style={styles.createButton}
                icon="plus"
              >
                创建目标
              </Button>
            </Card.Content>
          </Card>
        ) : (
          <View>
            <Card style={styles.planCard}>
              <Card.Content>
                <View style={styles.planHeader}>
                  <MaterialCommunityIcons name="target" size={32} color={theme.colors.primary} />
                  <Text variant="titleLarge" style={styles.planTitle}>
                    当前目标
                  </Text>
                </View>

                <View style={styles.goalInfo}>
                  <View style={styles.goalItem}>
                    <Text variant="bodySmall" style={styles.goalLabel}>目标体重</Text>
                    <Text variant="headlineMedium" style={styles.goalValue}>
                      {activePlan.targetWeight.toFixed(1)} kg
                    </Text>
                  </View>

                  <View style={styles.goalItem}>
                    <Text variant="bodySmall" style={styles.goalLabel}>当前体重</Text>
                    <Text variant="headlineMedium" style={styles.goalValue}>
                      {currentWeight?.toFixed(1) || '-'} kg
                    </Text>
                  </View>
                </View>

                <View style={styles.progressSection}>
                  <View style={styles.progressHeader}>
                    <Text variant="titleSmall">进度</Text>
                    {progress && (
                      <View
                        style={[
                          styles.statusBadge,
                          { backgroundColor: getStatusColor(progress.status) + '20' },
                        ]}
                      >
                        <Text
                          variant="bodySmall"
                          style={{ color: getStatusColor(progress.status), fontWeight: 'bold' }}
                        >
                          {getStatusText(progress.status)}
                        </Text>
                      </View>
                    )}
                  </View>

                  <ProgressBar
                    progress={progress ? Math.max(0, Math.min(1, progress.progressPercent / 100)) : 0}
                    color={getStatusColor(progress?.status)}
                    style={styles.progressBar}
                  />

                  <View style={styles.progressDetails}>
                    <Text variant="bodySmall">{progress?.progressPercent || 0}% 完成</Text>
                    <Text variant="bodySmall">
                      剩余 {activePlan ? differenceInDays(activePlan.targetDate, new Date()) : 0} 天
                    </Text>
                  </View>
                </View>

                <View style={styles.detailsSection}>
                  <View style={styles.detailItem}>
                    <MaterialCommunityIcons name="calendar" size={20} color="#757575" />
                    <Text variant="bodyMedium" style={styles.detailText}>
                      目标日期: {format(activePlan.targetDate, 'yyyy年MM月dd日')}
                    </Text>
                  </View>

                  {progress && (
                    <View style={styles.detailItem}>
                      <MaterialCommunityIcons name="scale-bathroom" size={20} color="#757575" />
                      <Text variant="bodyMedium" style={styles.detailText}>
                        预期体重: {progress.expectedWeight} kg
                      </Text>
                    </View>
                  )}
                </View>
              </Card.Content>
            </Card>

            <View style={styles.actionButtons}>
              <Button
                mode="outlined"
                onPress={() => setShowCreateDialog(true)}
                style={styles.actionButton}
                icon="plus"
              >
                新目标
              </Button>
              <Button
                mode="outlined"
                onPress={() => setShowHistoryDialog(true)}
                style={styles.actionButton}
                icon="history"
              >
                历史目标
              </Button>
            </View>
          </View>
        )}
      </ScrollView>

      {/* Create Plan Dialog */}
      <Portal>
        <Dialog visible={showCreateDialog} onDismiss={() => setShowCreateDialog(false)}>
          <Dialog.Title>创建体重目标</Dialog.Title>
          <Dialog.Content>
            <TextInput
              label="目标体重 (kg)"
              value={targetWeight}
              onChangeText={setTargetWeight}
              keyboardType="decimal-pad"
              mode="outlined"
              style={styles.formInput}
              right={<TextInput.Affix text="kg" />}
            />

            <TextInput
              label="起始体重 (kg) - 可选"
              value={startWeight}
              onChangeText={setStartWeight}
              keyboardType="decimal-pad"
              mode="outlined"
              style={styles.formInput}
              placeholder={currentWeight?.toString() || '自动使用当前体重'}
              right={<TextInput.Affix text="kg" />}
            />

            <View style={styles.dateInput}>
              <Text variant="bodyMedium" style={styles.dateLabel}>
                目标日期
              </Text>
              <Button
                mode="outlined"
                onPress={() => setShowDatePicker(true)}
                icon="calendar"
              >
                {format(targetDate, 'yyyy年MM月dd日')}
              </Button>
            </View>

            {showDatePicker && (
              <DateTimePicker
                value={targetDate}
                mode="date"
                display="default"
                minimumDate={new Date()}
                onChange={onDateChange}
              />
            )}

            {formError && <HelperText type="error">{formError}</HelperText>}
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setShowCreateDialog(false)} disabled={isSubmitting}>取消</Button>
            <Button
              onPress={handleCreatePlan}
              mode="contained"
              loading={isSubmitting}
              disabled={isSubmitting || !targetWeight}
            >
              创建
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      {/* History Dialog */}
      <Portal>
        <Dialog visible={showHistoryDialog} onDismiss={() => setShowHistoryDialog(false)} style={styles.historyDialog}>
          <Dialog.Title>历史目标</Dialog.Title>
          <Dialog.ScrollArea>
            <ScrollView contentContainerStyle={styles.historyContent}>
              {plans.length === 0 ? (
                <Text variant="bodyMedium" style={styles.emptyHistory}>暂无历史目标</Text>
              ) : (
                plans.map((plan) => (
                  <List.Item
                    key={plan.id}
                    title={`目标: ${plan.targetWeight.toFixed(1)} kg`}
                    description={`${format(plan.startDate, 'yyyy-MM-dd')} → ${format(plan.targetDate, 'yyyy-MM-dd')}`}
                    left={(props) => (
                      <List.Icon {...props} icon={plan.isActive ? 'target' : 'check-circle'} color={plan.isActive ? theme.colors.primary : '#4CAF50'} />
                    )}
                    right={(props) =>
                      !plan.isActive && (
                        <IconButton {...props} icon="delete" onPress={() => handleDeletePlan(plan.id)} />
                      )
                    }
                  />
                ))
              )}
            </ScrollView>
          </Dialog.ScrollArea>
          <Dialog.Actions>
            <Button onPress={() => setShowHistoryDialog(false)}>关闭</Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      <Snackbar
        visible={snackbarVisible}
        onDismiss={() => setSnackbarVisible(false)}
        duration={2000}
      >
        {snackbarMessage}
      </Snackbar>
    </View>
  );
}

// Need to import IconButton
import { IconButton } from 'react-native-paper';

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyCard: {
    margin: 16,
    marginTop: 32,
  },
  emptyContent: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  emptyTitle: {
    marginTop: 16,
    fontWeight: '600',
  },
  emptyText: {
    marginTop: 8,
    color: '#757575',
    textAlign: 'center',
  },
  createButton: {
    marginTop: 24,
  },
  planCard: {
    margin: 16,
  },
  planHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  planTitle: {
    marginLeft: 12,
    fontWeight: '600',
  },
  goalInfo: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 24,
  },
  goalItem: {
    alignItems: 'center',
  },
  goalLabel: {
    color: '#757575',
    marginBottom: 4,
  },
  goalValue: {
    fontWeight: 'bold',
  },
  progressSection: {
    marginBottom: 24,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
  },
  progressDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
  },
  detailsSection: {
    gap: 12,
  },
  detailItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  detailText: {
    marginLeft: 12,
  },
  actionButtons: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 12,
    marginHorizontal: 16,
    marginBottom: 16,
  },
  actionButton: {
    flex: 1,
  },
  formInput: {
    marginBottom: 16,
  },
  dateInput: {
    marginTop: 8,
  },
  dateLabel: {
    marginBottom: 8,
    color: '#757575',
  },
  historyDialog: {
    maxHeight: '70%',
  },
  historyContent: {
    paddingVertical: 8,
  },
  emptyHistory: {
    textAlign: 'center',
    color: '#757575',
    padding: 24,
  },
});
