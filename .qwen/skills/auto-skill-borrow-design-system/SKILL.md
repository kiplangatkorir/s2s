---
name: borrow-design-system
description: Systematic workflow for extracting a reference project's design language (colors, typography, animations, patterns) and applying it to a different codebase
source: auto-skill
extracted_at: '2026-06-19T14:36:15.766Z'
---

# Borrowing a Design System from a Reference Project

## When to use

When the user wants to apply the visual design of an existing project ("reference") to a new/different project — especially when the two projects use different frameworks or the reference has no formal design tokens.

## Workflow

### 1. Deep exploration of the reference project

Use an **explore agent** to thoroughly analyze the reference codebase. Request these specific deliverables:

- **CSS custom properties / theme tokens**: All `--var` definitions with exact hex values and usage
- **Typography**: Font families (display vs body), type scale (sizes, weights, line heights), heading patterns
- **Color palette**: Every color used — primary, accent, semantic (success/error), gray scale
- **Visual effects**: Shadows (exact values), border-radius, gradients, blur/backdrop-filter, glassmorphism
- **Animation patterns**: Easing curves, keyframe names, durations, micro-interactions (hover lifts, stagger reveals)
- **Component patterns**: How cards, buttons, inputs, and list items are styled (extract the actual class strings)
- **Layout conventions**: Container widths, padding, grid systems, responsive breakpoints

The agent should read: CSS/styling files, Tailwind config, layout components, key UI components, and any theme provider files.

### 2. Build the design token layer

Translate the extracted tokens into the target project's styling system. This typically means:

**CSS custom properties** (in `globals.css` or equivalent):
```css
:root {
  --foundation-dark: #0a0a0a;
  --accent-primary: #c2410c;
  --text-primary: #1c1917;
  --text-muted: #a8a29e;
  --border-subtle: #e7e5e4;
  /* ... full token set */
}
```

**Tailwind config extensions** (for framework-native usage):
```ts
theme: {
  extend: {
    colors: {
      foundation: { dark: "#0a0a0a", light: "#fafafa" },
      accent: { primary: "#c2410c", "primary-hover": "#ea580c" },
    },
    fontFamily: {
      serif: ["Playfair Display", "Georgia", "serif"],
      sans: ["Inter", "system-ui", "sans-serif"],
    },
    boxShadow: {
      "warm-sm": "0 4px 16px rgba(42, 30, 24, 0.06)",
    },
  },
}
```

**Keyframe animations** — port the reference's animation definitions verbatim, preserving easing curves and durations.

### 3. Identify and port utility classes

If the reference defines custom utility classes (e.g., `.glass`, `.glass-dark`, `.gradient-text`, `.skeleton`), port them to the target project's CSS. These encapsulate recurring visual patterns.

### 4. Apply consistently across all components

When building or rewriting components, use the ported tokens exclusively:
- Use `var(--text-primary)` not hardcoded `#1c1917`
- Use `shadow-warm-sm` not raw shadow values
- Use `font-serif` for headings, `font-sans` for body
- Apply the reference's micro-interaction patterns (hover lifts, focus rings, transitions)

### 5. Preserve interaction patterns, not just visuals

Design systems include behavior. Port these too:
- Button states (hover: `-translate-y-0.5`, focus: `outline 2px solid accent`)
- Card hover effects (shadow deepen, border color change)
- Input focus styles (border glow, shadow accent)
- Scroll behavior (custom scrollbar styling)
- Selection styling (`::selection`)

## Gotchas

- **Font loading**: The reference may load fonts via `@import` in CSS, a `<link>` in HTML, or a framework font optimizer. Match the target framework's convention (e.g., Next.js `next/font` vs Google Fonts `@import`).
- **Color opacity**: The reference may use `color-mix()` or `rgba()` with brand colors. Verify these work in the target CSS environment.
- **Animation easing**: The reference's custom cubic-bezier curves (e.g., `[0.16, 1, 0.3, 1]`) are part of its identity — port them exactly, don't substitute standard easings.
- **Cross-framework translation**: A Vite/React project may use CSS-in-JS or plain CSS, while the target uses Tailwind. Translate patterns, don't just copy class strings.
