---
name: postgres-best-practices
description: Apply PostgreSQL best practices for schema design, query performance, and safety. Use when designing database schemas, writing queries, or reviewing database code.
context: fork
agent: delivery-database-engineer
---

# PostgreSQL Best Practices

## Schema Design

### Types
```sql
-- Use appropriate types
id UUID PRIMARY KEY DEFAULT gen_random_uuid()
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
amount NUMERIC(10,2)  -- for money, never FLOAT
status TEXT CHECK (status IN ('active', 'inactive', 'pending'))

-- Avoid
id SERIAL  -- prefer UUID for distributed systems
created_at TIMESTAMP  -- always use TIMESTAMPTZ
amount FLOAT  -- floating point errors in money calculations
```

### Indexes
```sql
-- Create indexes for query patterns
CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders(user_id);
CREATE INDEX CONCURRENTLY idx_orders_created ON orders(created_at DESC);

-- Partial index for filtered queries
CREATE INDEX CONCURRENTLY idx_active_users ON users(email) WHERE deleted_at IS NULL;

-- Composite index — order matters: equality first, then range
CREATE INDEX idx_orders_user_status ON orders(user_id, status, created_at DESC);
```

**ALWAYS use CONCURRENTLY** when adding indexes in production — no table lock.

## Queries

### Avoid N+1
```sql
-- JOIN instead of separate queries per row
SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name;

-- N+1: one query per user — avoid
```

### Use EXPLAIN ANALYZE
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM orders WHERE user_id = $1 AND status = 'pending';
-- Look for: Seq Scan (bad for large tables), high actual rows vs estimated rows
```

### Pagination
```sql
-- Cursor-based (keyset) for large datasets
SELECT * FROM orders WHERE created_at < $cursor ORDER BY created_at DESC LIMIT 20;

-- OFFSET pagination degrades at high page numbers — avoid
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET $page * 20;
```

## Migrations

```sql
-- Always reversible
-- Up
ALTER TABLE users ADD COLUMN phone TEXT;
CREATE INDEX CONCURRENTLY idx_users_phone ON users(phone);

-- Down
DROP INDEX IF EXISTS idx_users_phone;
ALTER TABLE users DROP COLUMN IF EXISTS phone;

-- Never DROP COLUMN without a deprecation period
```

## Connection Pooling

Use PgBouncer or Supabase connection pooler:
- `pool_mode = transaction` for stateless web apps
- Never hold connections during long computations
- Set `statement_timeout` and `lock_timeout`

## Row Level Security (RLS)

```sql
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY posts_user_isolation ON posts
  USING (user_id = current_setting('app.user_id')::uuid);
```

## Checklist

- [ ] UUIDs as primary keys (not SERIAL)
- [ ] TIMESTAMPTZ (not TIMESTAMP) for all datetimes
- [ ] Indexes for all foreign keys and filter columns
- [ ] CONCURRENTLY for index creation in production
- [ ] EXPLAIN ANALYZE run on slow queries
- [ ] Migrations are reversible
- [ ] RLS enabled on multi-tenant tables
- [ ] NUMERIC (not FLOAT) for monetary amounts
