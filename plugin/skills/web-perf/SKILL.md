---
name: web-perf
description: Audit and improve Core Web Vitals and web performance. Use when optimizing page load speed, LCP, CLS, or INP metrics, or before production deployment.
context: fork
agent: delivery-performance-engineer
---

# Web Performance Audit

Measure first, optimize second. Never guess without data.

## Core Web Vitals Thresholds

| Metric | Good | Needs Work | Poor |
|--------|------|------------|------|
| LCP (Largest Contentful Paint) | < 2.5s | < 4s | > 4s |
| CLS (Cumulative Layout Shift) | < 0.1 | < 0.25 | > 0.25 |
| INP (Interaction to Next Paint) | < 200ms | < 500ms | > 500ms |
| TTFB (Time to First Byte) | < 800ms | < 1.8s | > 1.8s |

## Audit Process

### 1. Measure (Lighthouse)
```bash
npx lighthouse https://example.com --output json --output-path ./report.json
# Or: open Chrome DevTools → Lighthouse → Generate report
```

### 2. Identify the LCP Element
- Open DevTools → Performance → Record reload
- Find the largest image/text element that renders last
- Common culprits: hero images, above-fold text, carousels

### 3. Fix LCP
```html
<!-- Preload LCP image -->
<link rel="preload" as="image" href="/hero.webp" fetchpriority="high">

<!-- Avoid lazy loading above-fold images -->
<img src="/hero.webp" loading="eager" fetchpriority="high" width="1200" height="600" alt="Hero">

<!-- Lazy loading hero image — avoid -->
<img src="/hero.webp" loading="lazy" alt="Hero">
```

### 4. Fix CLS
```css
/* Reserve space for images */
img { width: 100%; height: auto; aspect-ratio: 16/9; }

/* Skeleton loaders for dynamic content */
.skeleton { width: 200px; height: 20px; background: #eee; }

/* Content that shifts when fonts/images load — avoid */
```

### 5. Eliminate Render-Blocking Resources
```html
<!-- Defer non-critical JS -->
<script src="analytics.js" defer></script>

<!-- Non-critical CSS via preload -->
<link rel="preload" href="non-critical.css" as="style" onload="this.rel='stylesheet'">

<!-- Synchronous JS in <head> — avoid -->
<script src="heavy-lib.js"></script>
```

### 6. Image Optimization
```bash
# Convert to WebP/AVIF
cwebp -q 80 input.jpg -o output.webp
ffmpeg -i input.jpg -c:v libavif -crf 30 output.avif

# Use next/image (Next.js), image CDN, or similar
```

Be specific: "compress hero.png (450KB) to WebP (target: <100KB)" not "optimize images."

### 7. Caching Headers
```
Cache-Control: public, max-age=31536000, immutable  # hashed assets
Cache-Control: public, max-age=3600                 # pages
Cache-Control: no-cache                             # API responses
```

## Output Format

```
## Performance Audit

**LCP**: X.Xs (Good/Needs Work/Poor)
**CLS**: X.XX (Good/Needs Work/Poor)
**INP**: Xms (Good/Needs Work/Poor)

### Issues (prioritized by impact)
1. **[HIGH]** Hero image not preloaded — adds ~800ms to LCP
   Fix: `<link rel="preload" as="image" href="/hero.webp" fetchpriority="high">`

2. **[MEDIUM]** 3 render-blocking scripts — add defer attribute

3. **[LOW]** Images not in WebP format — ~30% size reduction possible

### Wins Already in Place
- CDN in use
- Fonts preloaded
```
