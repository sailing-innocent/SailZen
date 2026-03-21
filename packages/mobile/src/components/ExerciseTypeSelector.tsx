import React from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { Card, Text, useTheme } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { ExerciseType } from '../db/schema';

interface ExerciseTypeSelectorProps {
  selectedType: ExerciseType | null;
  onSelect: (type: ExerciseType) => void;
}

const EXERCISE_TYPES: { type: ExerciseType; label: string; icon: string; color: string }[] = [
  { type: 'running', label: '跑步', icon: 'run', color: '#4CAF50' },
  { type: 'swimming', label: '游泳', icon: 'swim', color: '#2196F3' },
  { type: 'cycling', label: '骑行', icon: 'bike', color: '#FF9800' },
  { type: 'fitness', label: '健身', icon: 'dumbbell', color: '#9C27B0' },
  { type: 'yoga', label: '瑜伽', icon: 'meditation', color: '#E91E63' },
  { type: 'other', label: '其他', icon: 'dots-horizontal', color: '#757575' },
];

export function ExerciseTypeSelector({ selectedType, onSelect }: ExerciseTypeSelectorProps) {
  const theme = useTheme();

  return (
    <View style={styles.container}>
      <Text variant="titleSmall" style={styles.label}>
        选择运动类型
      </Text>
      <View style={styles.grid}>
        {EXERCISE_TYPES.map((item) => {
          const isSelected = selectedType === item.type;
          return (
            <TouchableOpacity
              key={item.type}
              onPress={() => onSelect(item.type)}
              style={[
                styles.typeButton,
                {
                  backgroundColor: isSelected ? item.color + '20' : theme.colors.surface,
                  borderColor: isSelected ? item.color : theme.colors.outline,
                  borderWidth: isSelected ? 2 : 1,
                },
              ]}
            >
              <MaterialCommunityIcons
                name={item.icon}
                size={28}
                color={isSelected ? item.color : theme.colors.onSurface}
              />
              <Text
                variant="bodySmall"
                style={[
                  styles.typeLabel,
                  { color: isSelected ? item.color : theme.colors.onSurface },
                ]}
              >
                {item.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
  },
  label: {
    marginBottom: 8,
    fontWeight: '600',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  typeButton: {
    width: '31%',
    aspectRatio: 1,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 12,
    marginBottom: 8,
  },
  typeLabel: {
    marginTop: 4,
  },
});
