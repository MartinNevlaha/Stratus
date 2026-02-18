---
name: react-best-practices
description: Apply React best practices for performance, correctness, and maintainability. Use when building or reviewing React applications.
context: fork
agent: delivery-frontend-engineer
---

# React Best Practices

## Critical: Eliminate Waterfalls

The most impactful performance issue. Never chain sequential async operations.

```tsx
// Waterfall: B starts only after A finishes
const user = await getUser(id);
const posts = await getPosts(user.id);

// Parallel: both start simultaneously
const [user, posts] = await Promise.all([getUser(id), getPosts(id)]);
```

## Component Design

### State Management
```tsx
// Derive state from existing state — don't duplicate
const filteredItems = useMemo(() => items.filter(i => i.active), [items]);

// Syncing state — avoid this
const [filteredItems, setFilteredItems] = useState([]);
useEffect(() => setFilteredItems(items.filter(i => i.active)), [items]);
```

### Avoid Unnecessary Re-renders
```tsx
// Memoize expensive components
const ExpensiveList = memo(({ items }: { items: Item[] }) => <List items={items} />);

// Stable references for callbacks
const handleClick = useCallback(() => doSomething(id), [id]);

// Memoize expensive calculations
const total = useMemo(() => items.reduce((sum, i) => sum + i.price, 0), [items]);
```

### Component Composition
```tsx
// Prefer composition over prop drilling
function Card({ children, header }: { children: React.ReactNode; header: React.ReactNode }) {
  return <div className="card"><div className="header">{header}</div>{children}</div>;
}

// Prop drilling through 3+ levels — use composition or context
```

## Bundle Size

```tsx
// Direct imports (treeshakeable)
import { format } from 'date-fns/format';

// Barrel imports (includes entire library) — avoid
import { format } from 'date-fns';

// Dynamic import for heavy components
const Chart = dynamic(() => import('./Chart'), { ssr: false });
```

## Error Boundaries

```tsx
// Every route/major section should have an error boundary
<ErrorBoundary fallback={<ErrorPage />}>
  <UserDashboard />
</ErrorBoundary>
```

## TypeScript

```tsx
// Explicit prop types
interface ButtonProps {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
}

// any props — avoid
function Button(props: any) { ... }
```

## Checklist

- [ ] No sequential awaits that could be parallel
- [ ] No useEffect for derived state
- [ ] Expensive components wrapped in memo()
- [ ] No barrel imports for large libraries
- [ ] Error boundaries at route level
- [ ] All props typed (no `any`)
- [ ] Keys on all list items (not index)
