import { Tabs } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTheme } from 'react-native-paper';

export default function TabLayout() {
  const theme = useTheme();

  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.colors.onSurfaceDisabled,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: '体重',
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="scale-bathroom" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="exercise"
        options={{
          title: '运动',
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="run" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="plan"
        options={{
          title: '目标',
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="target" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
