---
name: react-native-best-practices
description: Apply React Native performance patterns for smooth 60fps UIs. Use when building or reviewing React Native / Expo applications.
context: fork
agent: delivery-mobile-engineer
---

# React Native Best Practices

## List Performance (Most Common Issue)

```tsx
// FlatList with proper optimization
<FlatList
  data={items}
  keyExtractor={item => item.id}
  renderItem={({ item }) => <ItemRow item={item} />}  // memoized component
  getItemLayout={(_, index) => ({ length: 72, offset: 72 * index, index })}
  windowSize={5}
  maxToRenderPerBatch={10}
  initialNumToRender={15}
  removeClippedSubviews={true}
/>

// ScrollView for long lists — avoid (renders ALL items at once)
<ScrollView>{items.map(i => <ItemRow key={i.id} item={i} />)}</ScrollView>
```

## Memoization

```tsx
// Memoize list item components — prevents re-render on parent update
const ItemRow = memo(({ item }: { item: Item }) => {
  return <View><Text>{item.title}</Text></View>;
});

// Stable callbacks with useCallback
const onPress = useCallback(() => navigate('Detail', { id: item.id }), [item.id]);
```

## Native Driver for Animations

```tsx
// useNativeDriver: true — runs animation on native thread (60fps)
Animated.timing(opacity, {
  toValue: 1,
  duration: 300,
  useNativeDriver: true,  // ALWAYS for opacity, transform
}).start();

// useNativeDriver: false — JS thread, causes jank — avoid
```

## Image Optimization

```tsx
// Fast Image for network images with caching
import FastImage from 'react-native-fast-image';
<FastImage
  source={{ uri: url, priority: FastImage.priority.normal }}
  resizeMode={FastImage.resizeMode.cover}
/>

// Cache images in production — avoid re-downloading on scroll
```

## State Management

```tsx
// Zustand for simple global state
const useStore = create<Store>(set => ({
  user: null,
  setUser: (user) => set({ user }),
}));

// React Query for server state
const { data, isLoading } = useQuery({ queryKey: ['user', id], queryFn: () => fetchUser(id) });

// Heavy Redux setup for simple apps — avoid
```

## Navigation (React Navigation)

```tsx
// Screen options in navigator, not inside component
<Stack.Screen name="Detail" options={{ headerShown: false }} />

// Navigate with typed params
navigation.navigate('Detail', { id: item.id });

// Avoid inline functions in screenOptions
const screenOptions = useMemo(() => ({ headerShown: false }), []);
```

## Checklist

- [ ] FlatList (not ScrollView) for lists > 20 items
- [ ] keyExtractor returns unique string IDs (not index)
- [ ] getItemLayout set for fixed-height items
- [ ] Animations use useNativeDriver: true
- [ ] List items memoized with memo()
- [ ] Images cached (FastImage or Expo Image)
- [ ] No inline arrow functions in renderItem
