import React from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Card, Text, useTheme, Button } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface WeightStatisticsProps {
  avg: number | null;
  min: number | null;
  max: number | null;
  count: number;
  selectedPeriod: number;
  onPeriodChange: (days: number) => void;
}

const PERIODS = [
  { label: '7天', value: 7 },
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
  { label: '全部', value: 0 },
];

export function WeightStatistics({
  avg,
  min,
  max,
  count,
  selectedPeriod,
  onPeriodChange,
}: WeightStatisticsProps) {
  const theme = useTheme();

  const renderStatCard = (
    icon: string,
    label: string,
    value: string,
    color: string
  ) => (
    <Card style={[styles.statCard, { backgroundColor: color + '15' }]} key={label}>
      <Card.Content style={styles.statContent}>
        <MaterialCommunityIcons name={icon} size={24} color={color} />
        <Text variant="bodySmall" style={styles.statLabel}>{label}</Text>
        <Text variant="titleLarge" style={[styles.statValue, { color }]} numberOfLines={1}>
          {value}
        </Text>
      </Card.Content>
    </Card>
  );

  return (
    <View style={styles.container}>
      <View style={styles.periodSelector}>
        {PERIODS.map((period) => (
          <Button
            key={period.value}
            mode={selectedPeriod === period.value ? 'contained' : 'outlined'}
            onPress={() => onPeriodChange(period.value)}
            style={styles.periodButton}
            compact
          >
            {period.label}
          </Button>
        ))}
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statsContainer}>
        {renderStatCard(
          'scale',
          '平均体重',
          avg ? `${avg.toFixed(1)} kg` : '-',
          theme.colors.primary
        )}
        {renderStatCard(
          'arrow-down-bold',
          '最低体重',
          min ? `${min.toFixed(1)} kg` : '-',
          '#4CAF50'
        )}
        {renderStatCard(
          'arrow-up-bold',
          '最高体重',
          max ? `${max.toFixed(1)} kg` : '-',
          '#F44336'
        )}
        {renderStatCard(
          'format-list-numbered',
          '记录数',
          count.toString(),
          '#757575'
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
  periodButton: {
    minWidth: 60,
  },
  statsContainer: {
    paddingHorizontal: 4,
    gap: 8,
  },
  statCard: {
    minWidth: 100,
    marginRight: 8,
  },
  statContent: {
    alignItems: 'center',
    padding: 12,
  },
  statLabel: {
    marginTop: 4,
    color: '#757575',
  },
  statValue: {
    marginTop: 4,
    fontWeight: 'bold',
  },
});
