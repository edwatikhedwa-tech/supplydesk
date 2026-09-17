---
document_id: DOC-FRONTEND-UI-INVENTORY-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# UI Component Inventory

Evidence-based inventory of 13 UI primitive categories in `frontend-v2/src`, produced to explain
(not guess at) the "Frankenstein" complaint. Nothing here was changed.

| Component | Implementations | Used in | Differences | Recommended target | Migration risk |
|---|---|---|---|---|---|
| Button | 1 shared (`ui/Button.tsx`, variants primary/secondary/ghost) | Widely reused | None significant | Keep | Low |
| Input | **None shared** — raw `<input>` with copy-pasted Tailwind strings | `Blacklist.tsx`, `Suppliers.tsx`, `RequestDetail.tsx`, `Settings.tsx` (×2), `Requests.tsx`, `BulkComposeModal.tsx`, `LogisticsQuoteModal.tsx` (×7 in one file), `ContactResultModal.tsx`, `ManualLinkModal.tsx`, `TasksPanel.tsx` — 18+ occurrences | Small drifts: `h-8` vs `h-9`, `pl-7` vs `pl-8`, font sizes 12/12.5/13px. `Login.tsx` uses a **completely different palette** (`slate-950`, `blue-400`) not the app's design tokens at all | Extract `ui/Input.tsx`; fix Login to use tokens | Low-Med (mechanical, high count) |
| Select/Dropdown | Two unrelated systems: Radix-based `ui/select.tsx` (only used by `ConversationStatusSelect`) vs raw native `<select>` everywhere else | Native: `RequestDetail.tsx`, `Suppliers.tsx`, `SupplierCardContent.tsx`, `TasksSection.tsx` (×4) | Radix gives keyboard nav/portal/animation; native selects don't | Migrate native selects onto the Radix `Select`, or explicitly document native as a deliberate lightweight variant | Med (behavioral) |
| Checkbox | **None shared** — raw `<input type="checkbox">` | `Suppliers.tsx`, `RequestDetail.tsx` (×3), `Messages.tsx`, `Blacklist.tsx` (×2) | Inconsistent styling (`accent-accent` in some, unstyled in others) | Extract `ui/Checkbox.tsx` | Low |
| Card/panel | Two parallel patterns: `ui/Frame.tsx` (real component, used **only** in `Messages.tsx`) vs the hand-copied recipe `"rounded-lg border border-border bg-surface p-4"` | `Settings.tsx` (×6), `Help.tsx`, `Dashboard.tsx`, `Blacklist.tsx`, `Suppliers.tsx` | Drift: `p-4` vs `p-4 sm:p-5`, `rounded-lg` vs `rounded-xl` | Promote `FramePanel` (or a new `Card`) to a genuinely shared primitive | Low-Med |
| Table | **None shared** — 6 different `<table>` class strings | Suppliers (×2), Requests (uses `@tanstack/react-table`), RequestDetail, Blacklist, AiChatPanel | `@tanstack/react-table` is a real dependency used in exactly 1 of 6 — adopted mid-project, never backfilled | Standardize on one styled `<Table>` wrapper; decide tanstack's role | Med (layouts differ per table) |
| Tabs | 1 ad-hoc implementation (`SupplierCardPanel.tsx`, hand-built `role="tablist"`) | Only that one panel | Not yet a consistency problem — but no primitive exists if a second tabbed UI appears | Extract `ui/Tabs.tsx` pre-emptively | Low |
| Dialog/Modal | 1 shared (`ui/Modal.tsx`), genuinely reused | `NewRequestModal`, `ImportMailTopicModal`, `LogisticsQuoteModal`, `ContactResultModal`, `ManualLinkModal`, `BulkComposeModal` | **More consistent than assumed.** One real duplicate: `CommandPalette.tsx` re-implements ~15 lines of overlay shell instead of composing `Modal` | Keep `Modal` as standard; refactor `CommandPalette` to compose it | Low |
| Drawer | 1 ad-hoc mobile slide-over pattern (`Messages.tsx`) | Messages mobile layout only | Single bespoke usage | Not urgent | Low |
| Toast | 1 centralized system (`react-toastify`, single `<ToastContainer>` in `AppShell.tsx`) | App-wide reminders | **Consistent** | Keep | Low |
| Badge/status pill | `ui/Badge.tsx` (`Tone` system) **plus** a second, parallel hand-rolled `StatusPill` in `ConversationStatusSelect.tsx` re-typing the same tone→class mapping independently | Badge: broad. StatusPill: only conversation status | Confirms the owner's specific suspicion — a duplicate status-rendering path exists | Have `StatusPill` render `<Badge tone=... variant="outline">` instead | Low |
| Loading state | `LoadingState` (exported from `ErrorState.tsx` — odd co-location) | 12 files broadly adopt it | Adoption is good; organization is the only issue | Move to its own file or a combined `states.ts` | Low |
| Empty state | `ui/EmptyState.tsx`, shared | Same 12-file set | Consistent | Keep | Low |
| Error state | `ui/ErrorState.tsx`, shared, uses `Button` for retry | Same 12-file set | Consistent | Keep | Low |

## Cross-cutting findings

- **Icons:** `lucide-react` exclusively, 41 files, no competing icon source. Not a Frankenstein
  symptom.
- **Styling:** ~100% Tailwind utility classes. The one real outlier is `MagicRings.tsx`
  (Three.js/GLSL shader, `MagicRings.css`) used exclusively by `Login.tsx` — pulls the entire
  `three` package for one decorative background.
- **`Login.tsx`** uses literal colors (`slate-950`, `blue-400`, `white/20`) instead of the app's
  design tokens (`bg-surface`, `text-ink`, `accent-*`) used everywhere else — combined with the
  shader background, it reads as imported from a different design source than the rest of
  `frontend-v2`.
- **A second, independent legacy UI system still exists** in `frontend/src/components/ui/`
  (`Button.tsx`, `StatusBadge.tsx`, `MailStatusBadges.tsx`) — not live, but its continued presence
  is itself Frankenstein evidence if anyone edits it by mistake.

## Honest counterpoint

Button, Badge (mostly), Modal, the Loading/Empty/Error trio, the toast system, and icon usage are
each genuinely centralized and broadly reused — better than "everything is duplicated" implies.
The real, narrow pattern: **no shared primitive exists yet for Input, Checkbox, Card, Table, or
Tabs**, so every page reinvents those five independently, plus two concrete duplicate-instead-of-
compose cases (`StatusPill`, `CommandPalette`'s overlay) and one visually foreign page (`Login`).

Recorded gaps: `GAP-005` through `GAP-009` in [`../system/KNOWN_GAPS.md`](../system/KNOWN_GAPS.md).
