# Theme context

## Token summary

- Paper: `#F6F5F0`
- Surface: `#FFFEFB`
- Ink: `#10212A`
- Muted text: `#53656C`
- Faint text: `#7B8E94`
- Teal accent: `#0F6B5D`
- Teal accent strong: `#0A4F46`
- Amber signal: `#E18B2A`
- Success: `#167053`
- Warning: `#A7670C`
- Danger: `#A54234`
- Font display: `Golos Text`
- Font body: `IBM Plex Sans`
- Font utility: `IBM Plex Mono`
- Radii: `10px`, `16px`, `22px`
- Shadow: `0 1px 2px rgba(16,33,42,.05), 0 18px 44px -30px rgba(16,33,42,.42)`
- Breakpoints: `900px`, `640px`, `560px`

## Current source tokens

```css
:root {
  --paper:#F6F5F0; --surface:#FFFEFB; --sunk:#EAF0ED; --edge:#D5DFDB; --edge-hi:#AEBEB8;
  --text:#10212A; --soft:#53656C; --faint:#7B8E94;
  --accent:#0F6B5D; --accent-bg:#DCEEE9; --accent-hi:#0A4F46;
  --signal:#E18B2A; --signal-bg:#F8EAD4;
  --ok:#167053; --ok-bg:#DCEFE7; --warn:#A7670C; --warn-bg:#F7E8C9; --stop:#A54234; --stop-bg:#F3DFDA;
  --radius-sm:10px; --radius-md:16px; --radius-lg:22px;
}
```

## Styling source

All selectors and responsive rules live in the `<style>` block of `supplier_finder.html`. The redesign should preserve the token-first approach, typography pairing, semantic colors, visible focus state, reduced-motion support, and mobile touch target sizing.
