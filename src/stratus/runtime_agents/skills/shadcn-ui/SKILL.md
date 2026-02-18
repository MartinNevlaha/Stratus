---
name: shadcn-ui
description: Build UI components using shadcn/ui. Use when implementing UI with the shadcn/ui component library, Radix UI primitives, and Tailwind CSS.
context: fork
agent: delivery-frontend-engineer
---

# shadcn/ui Component Integration

shadcn/ui is **not a component library** — it's reusable components you copy into your project. Full ownership, full customization.

## Install Components

```bash
# Add a component
npx shadcn@latest add button
npx shadcn@latest add card dialog input

# Initialize in new project
npx shadcn@latest init
```

Components land in `components/ui/`. Modify them freely.

## Project Setup

```
src/
├── components/
│   ├── ui/              # shadcn components (auto-generated)
│   └── [custom]/        # your composed components
├── lib/
│   └── utils.ts         # cn() utility
```

### The `cn()` Utility (required)

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

## Composition Patterns

### Custom Variants

```typescript
import { cva } from "class-variance-authority";

const buttonVariants = cva("inline-flex items-center justify-center rounded-md", {
  variants: {
    variant: {
      default: "bg-primary text-primary-foreground hover:bg-primary/90",
      outline: "border border-input bg-background hover:bg-accent",
      ghost: "hover:bg-accent hover:text-accent-foreground",
    },
    size: {
      default: "h-10 px-4 py-2",
      sm: "h-9 px-3",
      lg: "h-11 px-8",
    },
  },
  defaultVariants: { variant: "default", size: "default" },
});
```

### Extending Components

```typescript
// Wrap, don't modify the ui/ source
import { Button, ButtonProps } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

export function LoadingButton({ loading, children, ...props }: ButtonProps & { loading?: boolean }) {
  return (
    <Button disabled={loading} {...props}>
      {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
      {children}
    </Button>
  );
}
```

## Common Components

```typescript
// Form
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Dialog
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

// Data display
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

// Feedback
import { toast } from "@/components/ui/use-toast";
```

## Theme Customization

```css
/* globals.css */
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --radius: 0.5rem;
  }
  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
  }
}
```

## Checklist

- [ ] `npx shadcn@latest init` run in project
- [ ] `cn()` utility in `lib/utils.ts`
- [ ] Components in `components/ui/` (not modified manually)
- [ ] Custom components in `components/` (wrap, don't edit ui/)
- [ ] `tsconfig.json` has `@` path alias
- [ ] Dark mode tested
- [ ] Keyboard navigation verified
