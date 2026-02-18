---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces. Use when building web components, pages, dashboards, landing pages, or any UI that needs strong visual design.
context: fork
agent: delivery-frontend-engineer
---

# Frontend Design

Create production-grade, visually distinctive frontend code. Avoid generic AI aesthetics.

## Design Thinking First

Before writing a single line of code, commit to a **bold aesthetic direction**:

- **Purpose**: What problem does this solve? Who uses it?
- **Tone**: Choose decisively — brutally minimal, maximalist, retro-futuristic, editorial, art deco, organic, luxury, brutalist. Execute with precision.
- **Differentiation**: What makes this UNFORGETTABLE?

## Implementation Standards

### Typography
- Avoid generic fonts (Inter, Roboto, Arial, system fonts)
- Pair a distinctive display font with a refined body font
- Use fonts that are characterful and unexpected

### Color & Theme
- CSS variables for consistency: `--primary`, `--accent`, `--surface`
- Dominant color + sharp accent beats timid palettes
- Commit fully: either high-contrast or monochromatic, not both

### Motion
- CSS transitions for micro-interactions
- One well-orchestrated page load > scattered animations
- Hover states that delight without annoying

### Layout
- Break the grid intentionally
- Generous negative space OR controlled density — pick one
- Asymmetry, overlap, diagonal flow where appropriate

## Anti-Patterns to Avoid

- Purple gradients on white backgrounds
- Generic card components with rounded corners everywhere
- System fonts
- "Clean and minimal" that's just empty
- Copying common UI patterns without intentionality

## Output Format

1. Working, production-ready code (HTML/CSS/JS, React, Vue, etc.)
2. Responsive by default
3. Accessible: proper contrast ratios, keyboard navigation, ARIA where needed
4. Self-contained where possible (no missing dependencies)
