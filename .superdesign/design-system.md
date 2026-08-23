# Supplier Finder — visual direction

## Product context

Supplier Finder is a procurement workspace for a buyer who needs to move from a material request to a shortlist of trustworthy suppliers. The primary job is comparison: see evidence, coverage, confidence, and contact data without losing the request context.

## Design intent

Create a confident, modern B2B product surface with an editorial command-center feel. It should feel like a calm, high-signal instrument rather than a generic dashboard. Keep the existing Russian content and behavior, but make the hierarchy, density, and states more legible.

## Visual language

Adopt the single `Mosaic Grid Architecture Style` source: technical minimalism inspired by blueprints and high-end wireframes.

- Background: warm paper `#F7F7F5`; cards use near-white `#FFFEFB`.
- Brand shell: deep forest/blue-green `#1A3C2B` / `#10212A`.
- Primary action: forest green `#1A3C2B`; hover `#0E2A1E`.
- Signature accents: coral `#FF8C69`, mint `#9EFFBF`, and gold `#F4D35E`.
- Semantic colors remain separate: success green, warning gold, danger terracotta.
- Typography: `Golos Text` for display/headings, `IBM Plex Sans` for body, `IBM Plex Mono` for domains/metadata. Do not add decorative fonts.
- Layout: structural grid, strong horizontal rules, asymmetric request summary, compact filter control surface, evidence-first supplier cards.
- Surfaces: 1px hairline borders, 0–2px radii, no large shadows, flat color blocks, clear negative space.
- Motion: crisp 150ms state changes; no animation that competes with evidence.
- Avoid: purple gradients, generic SaaS hero art, excessive glassmorphism, dense tiny text, decorative imagery that competes with supplier evidence.

## Responsive behavior

- Use container-aware card layout where possible; cards stack their evidence column below the main content when narrow.
- Filters collapse to one column on narrow mobile widths.
- Maintain touch targets around 42px minimum and visible focus rings.
- Preserve reading order: request → filters → confirmed suppliers → possible suppliers.

## Motion

- Short 150–180ms elevation/opacity transitions for cards and controls.
- Use view-transition-style fade/slide only for list updates if supported; always provide a reduced-motion fallback.

## Accessibility

- Use WCAG 2.2 AA contrast targets for text and controls.
- Keep `:focus-visible` indicators high-contrast and not obscured.
- Preserve semantic headings, labels, checkbox names, and dialog semantics.
