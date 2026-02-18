---
name: next-best-practices
description: Apply Next.js App Router best practices for Server Components, caching, and performance. Use when building or reviewing Next.js 13+ applications.
context: fork
agent: delivery-frontend-engineer
---

# Next.js Best Practices (App Router)

## Server vs Client Components

```tsx
// Server Component (default) — no 'use client'
// Runs on server: can fetch data, access DB, no event handlers
async function UserProfile({ id }: { id: string }) {
  const user = await db.getUser(id);  // direct DB access
  return <div>{user.name}</div>;
}

// Client Component — only when needed
'use client';
// Needs: useState, useEffect, event handlers, browser APIs
function SearchBar() {
  const [query, setQuery] = useState('');
  return <input onChange={e => setQuery(e.target.value)} />;
}
```

**Push 'use client' to leaves.** Never put 'use client' at layout level.

## Data Fetching

```tsx
// Fetch in Server Components, pass to Client as props
async function Page() {
  const data = await fetchData();  // cached by Next.js
  return <ClientChart data={data} />;  // client only for interactivity
}

// Parallel fetching — never sequential in components
async function Dashboard() {
  const [user, metrics, alerts] = await Promise.all([
    getUser(), getMetrics(), getAlerts()
  ]);
  return <Layout user={user} metrics={metrics} alerts={alerts} />;
}
```

## Caching

```tsx
// Default: cached indefinitely (static)
fetch('https://api.example.com/data')

// Revalidate every 60 seconds
fetch('https://api.example.com/data', { next: { revalidate: 60 } })

// Never cache (dynamic)
fetch('https://api.example.com/data', { cache: 'no-store' })
```

### `unstable_cache` for DB queries

```tsx
import { unstable_cache } from 'next/cache';

const getCachedUser = unstable_cache(
  async (id: string) => db.getUser(id),
  ['user'],
  { revalidate: 3600, tags: ['user'] }
);
```

## Route Handlers

```typescript
// app/api/users/route.ts
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');
  const user = await db.getUser(id!);
  return Response.json(user);
}
```

## Image Optimization

```tsx
// Always use next/image
import Image from 'next/image';
<Image src="/hero.jpg" alt="Hero" width={800} height={400} priority />

// Never use <img> directly for content images
```

## Loading & Error UI

```
app/
├── dashboard/
│   ├── page.tsx      # main content
│   ├── loading.tsx   # automatic Suspense boundary
│   └── error.tsx     # error boundary
```

## Checklist

- [ ] Server Components by default, Client only at leaves
- [ ] No sequential awaits — use Promise.all
- [ ] Images use next/image with explicit dimensions
- [ ] Caching strategy set for each fetch
- [ ] loading.tsx and error.tsx at each route segment
- [ ] Metadata exported from page.tsx
- [ ] No client-side data fetching when Server Component would work
