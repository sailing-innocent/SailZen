import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Card, Text, IconButton, useTheme, Menu } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { ExerciseRecord, ExerciseType } from '../db/schema';
import { format, isSameDay, isYesterday, startOfWeek, differenceInDays } from 'date-fns';
import { zhCN } from 'date-fns/locale';

interface ExerciseHistoryListProps {
  exercises: ExerciseRecord[];
  onEdit: (exercise: ExerciseRecord) => void;
  onDelete: (id: number) => void;
  loading?: boolean;
}

const TYPE_LABELS: Record<ExerciseType, string> = {
  running: '跑步',
  swimming: '游泳',
  cycling: '骑行',
  fitness: '健身',
  yoga: '瑜伽',
  other: '其他',
};

const TYPE_ICONS: Record<ExerciseType, string> = {
  running: 'run',
  swimming: 'swim',
  cycling: 'bike',
  fitness: 'dumbbell',
  yoga: 'meditation',
  other: 'dots-horizontal',
};

const TYPE_COLORS: Record<ExerciseType, string> = {
  running: '#4CAF50',
  swimming: '#2196F3',
  cycling: '#FF9800',
  fitness: '#9C27B0',
  yoga: '#E91E63',
  other: '#757575',
};

function formatDateGroup(date: Date): string {
  const now = new Date();
  
  if (isSameDay(date, now)) {
    return '今天';
  } else if (isYesterday(date)) {
    return '昨天';
  } else if (differenceInDays(now, date) < 7) {
    return format(date, 'EEEE', { locale: zhCN });
  } else {
    return format(date, 'MM月dd日');
  }
}

function groupExercisesByDate(exercises: ExerciseRecord[]): Map<string, ExerciseRecord[]> {
  const groups = new Map<string, ExerciseRecord[]>();
  
  exercises.forEach((exercise) => {
    const dateKey = formatDateGroup(exercise.recordTime);
    if (!groups.has(dateKey)) {
      groups.set(dateKey, []);
    }
    groups.get(dateKey)!.push(exercise);
  });
  
  return groups;
}

function ExerciseItem({
  exercise,
  onEdit,
  onDelete,
}: {
  exercise: ExerciseRecord;
  onEdit: (exercise: ExerciseRecord) => void;
  onDelete: (id: number) => void;
}) {
  const theme = useTheme();
  const [menuVisible, setMenuVisible] = React.useState(false);
  const iconColor = TYPE_COLORS[exercise.type];

  return (
    <Card style={styles.itemCard}>
      <Card.Content style={styles.itemContent}>
        <View style={[styles.iconContainer, { backgroundColor: iconColor + '15' }]} key={exercise.id}>
          <MaterialCommunityIcons
            name={TYPE_ICONS[exercise.type]}
            size={24}
            color={iconColor}
          />
        </View>

        <View style={styles.info}>
          <Text variant="titleSmall" style={styles.typeLabel}>
            {TYPE_LABELS[exercise.type]}
          </Text>
          <View style={styles.details}>
            <Text variant="bodySmall" style={styles.detailText}>
              {exercise.duration} 分钟
            </Text>
            <Text variant="bodySmall" style={[styles.detailText, styles.calories]}>
              {exercise.calories} kcal
            </Text>
          </View>
        </View>

        <View style={styles.actions}>
          {exercise.syncStatus === 'pending' && (
            <MaterialCommunityIcons
              name="cloud-upload-outline"
              size={16}
              color="#FF9800"
              style={styles.syncIcon}
            />
          )}
          <Text variant="bodySmall" style={styles.time}>
            {format(exercise.recordTime, 'HH:mm')}
          </Text>

          <Menu
            visible={menuVisible}
            onDismiss={() => setMenuVisible(false)}
            anchor={
              <IconButton
                icon="dots-vertical"
                size={20}
                onPress={() => setMenuVisible(true)}
              />
            }
          >
            <Menu.Item
              onPress={() => {
                setMenuVisible(false);
                onEdit(exercise);
              }}
              title="编辑"
              leadingIcon="pencil"
            />
            <Menu.Item
              onPress={() => {
                setMenuVisible(false);
                onDelete(exercise.id);
              }}
              title="删除"
              leadingIcon="delete"
              titleStyle={{ color: theme.colors.error }}
            />
          </Menu>
        </View>
      </Card.Content>
    </Card>
  );
}

export function ExerciseHistoryList({
  exercises,
  onEdit,
  onDelete,
  loading,
}: ExerciseHistoryListProps) {
  if (exercises.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <MaterialCommunityIcons name="run" size={64} color="#E0E0E0" />
        <Text variant="bodyLarge" style={styles.emptyText}>
          暂无运动记录
        </Text>
        <Text variant="bodySmall" style={styles.emptySubtext}>
          点击上方按钮添加第一条运动记录
        </Text>
      </View>
    );
  }

  const grouped = groupExercisesByDate(exercises);

  return (
    <View style={styles.container}>
      {Array.from(grouped.entries()).map(([dateGroup, groupExercises]) => (
        <View key={dateGroup} style={styles.group}>
          <Text variant="titleSmall" style={styles.groupHeader}>
            {dateGroup}
          </Text>
          {groupExercises.map((exercise) => (
            <ExerciseItem
              key={exercise.id}
              exercise={exercise}
              onEdit={onEdit}
              onDelete={onDelete}
            />
          ))}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
  },
  group: {
    marginBottom: 16,
  },
  groupHeader: {
    marginBottom: 8,
    fontWeight: '600',
    color: '#757575',
  },
  itemCard: {
    marginBottom: 8,
    elevation: 1,
  },
  itemContent: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
  },
  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  info: {
    flex: 1,
    marginLeft: 12,
  },
  typeLabel: {
    fontWeight: '600',
  },
  details: {
    flexDirection: 'row',
    marginTop: 2,
  },
  detailText: {
    color: '#757575',
  },
  calories: {
    marginLeft: 12,
    color: '#FF5722',
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  syncIcon: {
    marginRight: 4,
  },
  time: {
    color: '#9E9E9E',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 48,
  },
  emptyText: {
    marginTop: 16,
    color: '#757575',
  },
  emptySubtext: {
    marginTop: 8,
    color: '#9E9E9E',
  },
});
