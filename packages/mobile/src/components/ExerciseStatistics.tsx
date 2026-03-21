import React from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Card, Text, useTheme } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface ExerciseStatisticsProps {
  totalDuration: number | null;
  totalCalories: number | null;
  count: number;
  period: 'week' | 'month' | 'year';
  onPeriodChange: (period: 'week' | 'month' | 'year') => void;
}

const PERIODS = [
  { label: '本周', value: 'week' as const },
  { label: '本月', value: 'month' as const },
  { label: '本年', value: 'year' as const },
];

export function ExerciseStatistics({
  totalDuration,
  totalCalories,
  count,
  period,
  onPeriodChange,
}: ExerciseStatisticsProps) {
  const theme = useTheme();

  const renderStatCard = (
    icon: string,
    label: string,
    value: string,
    color: string
  ) => (
    <Card style={[styles.statCard, { backgroundColor: color + '15' }]} key={label}>
      <Card.Content style={styles.statContent}>
        <MaterialCommunityIcons name={icon} size={28} color={color} />
        <Text variant="titleLarge" style={[styles.statValue, { color }]} numberOfLines={1}>
          {value}
        </Text>
        <Text variant="bodySmall" style={styles.statLabel}>{label}</Text>
      </Card.Content>
    </Card>
  );

  const formatDuration = (minutes: number | null): string => {
    if (minutes === null) return '-';
    if (minutes < 60) return `${minutes}分钟`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hours}小时${mins}分` : `${hours}小时`;
  };

  return (
    <View style={styles.container}>
      <View style={styles.periodSelector}>
        {PERIODS.map((p) => (
          <Card
            key={p.value}
            style={[
              styles.periodCard,
              period === p.value && { backgroundColor: theme.colors.primaryContainer },
            ]}
            onPress={() => onPeriodChange(p.value)}
          >
            <Card.Content style={styles.periodContent}>
              <Text
                variant="bodyMedium"
                style={[
                  styles.periodText,
                  period === p.value && { color: theme.colors.onPrimaryContainer, fontWeight: 'bold' },
                ]}
              >
                {p.label}
              </Text>
            </Card.Content>
          </Card>
        ))}
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statsContainer}>
        {renderStatCard(
          'dumbbell',
          '运动次数',
          count.toString(),
          theme.colors.primary
        )}
        {renderStatCard(
          'clock-outline',
          '总时长',
          formatDuration(totalDuration),
          '#4CAF50'
        )}
        {renderStatCard(
          'fire',
          '消耗热量',
          totalCalories !== null ? `${totalCalories} kcal` : '-',
          '#FF5722'
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
  },
  periodSelector: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: 12,
    gap: 8,
  },
  periodCard: {
    minWidth: 80,
    elevation: 0,
  },
  periodContent: {
    padding: 8,
    alignItems: 'center',
  },
  periodText: {
    color: '#757575',
  },
  statsContainer: {
    paddingHorizontal: 4,
    gap: 8,
  },
  statCard: {
    minWidth: 110,
    marginRight: 8,
  },
  statContent: {
    alignItems: 'center',
    padding: 12,
  },
  statValue: {
    marginTop: 8,
    fontWeight: 'bold',
  },
  statLabel: {
    marginTop: 4,
    color: '#757575',
  },
});
