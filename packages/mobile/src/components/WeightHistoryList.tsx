import React from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { Card, Text, IconButton, useTheme, Menu } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { WeightRecord } from '../db/schema';
import { format } from 'date-fns';
import { zhCN } from 'date-fns/locale';

interface WeightHistoryListProps {
  weights: WeightRecord[];
  onEdit: (weight: WeightRecord) => void;
  onDelete: (id: number) => void;
  loading?: boolean;
}

function formatDate(date: Date): string {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const recordDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  
  const diffDays = Math.floor((today.getTime() - recordDate.getTime()) / (1000 * 60 * 60 * 24));
  
  if (diffDays === 0) {
    return `今天 ${format(date, 'HH:mm')}`;
  } else if (diffDays === 1) {
    return `昨天 ${format(date, 'HH:mm')}`;
  } else if (diffDays < 7) {
    return format(date, 'EEE HH:mm', { locale: zhCN });
  } else {
    return format(date, 'MM-dd HH:mm');
  }
}

function WeightItem({
  weight,
  onEdit,
  onDelete,
}: {
  weight: WeightRecord;
  onEdit: (weight: WeightRecord) => void;
  onDelete: (id: number) => void;
}) {
  const theme = useTheme();
  const [menuVisible, setMenuVisible] = React.useState(false);

  return (
    <Card style={styles.itemCard}>
      <Card.Content style={styles.itemContent}>
        <View style={styles.weightInfo}>
          <Text variant="titleLarge" style={styles.weightValue}>
            {weight.value.toFixed(1)}
          </Text>
          <Text variant="bodyMedium" style={styles.weightUnit}>
            kg
          </Text>
        </View>

        <View style={styles.dateContainer}>
          <MaterialCommunityIcons
            name="clock-outline"
            size={14}
            color="#757575"
          />
          <Text variant="bodySmall" style={styles.dateText}>
            {formatDate(weight.recordTime)}
          </Text>
        </View>

        <View style={styles.actions}>
          {weight.syncStatus === 'pending' && (
            <MaterialCommunityIcons
              name="cloud-upload-outline"
              size={16}
              color="#FF9800"
              style={styles.syncIcon}
            />
          )}
          
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
                onEdit(weight);
              }}
              title="编辑"
              leadingIcon="pencil"
            />
            <Menu.Item
              onPress={() => {
                setMenuVisible(false);
                onDelete(weight.id);
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

export function WeightHistoryList({
  weights,
  onEdit,
  onDelete,
  loading,
}: WeightHistoryListProps) {
  if (weights.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <MaterialCommunityIcons name="scale-off" size={64} color="#E0E0E0" />
        <Text variant="bodyLarge" style={styles.emptyText}>
          暂无体重记录
        </Text>
        <Text variant="bodySmall" style={styles.emptySubtext}>
          点击上方按钮添加第一条记录
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text variant="titleMedium" style={styles.sectionTitle}>
        历史记录
      </Text>
      {weights.map((weight) => (
        <WeightItem
          key={weight.id}
          weight={weight}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
  },
  sectionTitle: {
    marginBottom: 12,
    fontWeight: '600',
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
  weightInfo: {
    flexDirection: 'row',
    alignItems: 'baseline',
    minWidth: 80,
  },
  weightValue: {
    fontWeight: 'bold',
  },
  weightUnit: {
    marginLeft: 2,
    color: '#757575',
  },
  dateContainer: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 16,
  },
  dateText: {
    marginLeft: 4,
    color: '#757575',
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  syncIcon: {
    marginRight: 8,
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
