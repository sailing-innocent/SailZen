import { View, StyleSheet } from 'react-native';
import { Text, Card, Button } from 'react-native-paper';

export default function WeightScreen() {
  return (
    <View style={styles.container}>
      <Card style={styles.card}>
        <Card.Title title="体重记录" />
        <Card.Content>
          <Text variant="bodyLarge">今日体重: -- kg</Text>
        </Card.Content>
        <Card.Actions>
          <Button mode="contained">记录体重</Button>
        </Card.Actions>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f5f5f5',
  },
  card: {
    marginBottom: 16,
  },
});
