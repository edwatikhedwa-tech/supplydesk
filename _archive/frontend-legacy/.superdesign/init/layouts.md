# Layout inventory

## Supplier Finder shell
- Source: `supplier_finder.html`
- Description: standalone page shell with sticky application header, request summary, filters, two result groups, toast stack, and modal export dialog.

```html
<body>
  <div class="topbar">
    <div class="topbar-in">
      <div class="brand"><span class="mark">П</span> Поиск поставщиков</div>
      <div class="sep"></div>
      <div class="order">Заявка № 1043 · Снабжение · 20.08.2026</div>
      <div class="right">
        <span class="pill" id="statePill" aria-live="polite"><span class="dot"></span> Поиск завершён</span>
        <button class="btn ghost" id="demoToggle">Показать ход поиска</button>
      </div>
    </div>
  </div>

  <div class="wrap">
    <div class="progress" id="progress">...</div>
    <div class="order-head">...</div>
    <div class="controls">...</div>
    <div class="block" id="blockOk"><div class="cards" id="cardsOk"></div></div>
    <div class="block" id="blockMaybe"><div class="cards" id="cardsMaybe"></div></div>
  </div>

  <div class="toasts" id="toasts"></div>
  <div class="sheet" id="sheet" role="dialog" aria-modal="true">...</div>
</body>
```
