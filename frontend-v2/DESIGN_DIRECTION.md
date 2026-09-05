# SupplyDesk Frontend V2 — Design Direction v1

Mode: **CREATE** (greenfield). Written before substantial implementation, per the
frontend-product-engineer skill's Design Director gate. This direction governs
the App Shell, Dashboard, Requests, Suppliers and Messages screens built in
this first slice.

## Product personality and emotional target

SupplyDesk is the daily operating surface for a procurement specialist
(снабженец) who runs many concurrent supplier-sourcing requests (заявки) by
email, and is judged on whether nothing slips: deadlines, unanswered
suppliers, unread replies. The product should feel like **calm operational
control** — a dispatcher's console, not a decorated dashboard and not a
generic admin template. Nothing should compete visually with "what needs my
attention right now."

## Visual identity statement

A light, restrained, typography-led B2B surface: a persistent dark-graphite
navigation rail for continuity across screens, single-line dense rows for
homogeneous lists (requests, suppliers), one accent color reserved for
primary actions and active state, and a small semantic-color vocabulary
(danger/warning/success/info) that only ever encodes meaning — never
decoration. Numbers and dates use tabular figures everywhere they appear in a
list, so columns of counts and deadlines line up and can be scanned instead
of read.

## Visual thesis

The job is triage under time pressure across a large number of similar
records (requests, suppliers, threads). Cards force one item into a large
visual unit and waste the scan; a dense list/table lets the eye run down a
column. Color must be reserved for urgency and status, or the moment a
request goes red loses meaning against everything else that's already
colorful. A dark rail (vs. a light one) gives the four primary destinations a
fixed, low-noise anchor that never competes with page content, which is
where all the color and urgency signaling has to live.

## Information hierarchy and reading order

1. Navigation rail (which product area) — always present, minimal weight.
2. Page header (what this screen is, one primary action) — one line.
3. Urgency/status signal (deadline color, unread dot, response-rate) — the
   first thing scanned inside a row, left-weighted.
4. Identity (request name, supplier/company name) — second scan stop.
5. Supporting metadata (counts, dates, secondary badges) — right-aligned,
   de-emphasized, tabular.

## Spatial / compositional strategy

Information-rich density for Requests and Suppliers (rows ~44–48px, tight
vertical rhythm, no card padding tax). Dashboard is balanced density: short
grouped lists, not dense tables, because it is a triage feed rather than a
searchable record set. Messages is calm density: generous reading width for
message bodies, dense navigator on the left.

## Typography

- Display/heading role: **ProcureSans** (self-hosted `Semibold` for page
  titles and the wordmark, `Regular` for section headings) — the one
  deliberately distinctive typographic choice, used only at sizes ≥16px
  where its character reads clearly and never for dense data.
- UI/body/data role: **Inter**, for everything dense — table cells, labels,
  form controls, message bodies — because it has reliable tabular figures,
  a tall x-height at small sizes, and predictable metrics at 12–14px.
- Line-length rule: message bodies cap at ~72ch; table cells never wrap to
  more than 2 lines (truncate with a title attribute beyond that).

## Surfaces, border, radius, elevation, color

- Canvas: near-white neutral (`#F7F7F8`), not pure white, so white surfaces
  (rows on hover, panels, the composer) have something to sit on.
- Borders over shadows: 1px hairline dividers separate rows and panels;
  elevation is reserved for the one truly floating layer (dialogs, menus)
  and stays small (`shadow-sm`/`shadow-md`, never a soft glow).
- Radius: 6–8px on controls and panels — enough to soften a dense screen,
  not enough to read as playful.
- One accent (indigo, `#4F46E5` family) for primary buttons, links, active
  nav, focus rings. Semantic ramps (danger/warning/success/info) are
  separate hues, used only on status badges, deadline chips and unread
  indicators — never as a decorative background.

## Navigation and interaction character

Persistent left rail, collapsible to an icon-only rail. No top bar — a
second horizontal chrome band was considered and rejected: with a rail
already carrying navigation and a page header already carrying the screen's
identity and primary action, a top bar would only repeat one of the two.
Instead, global search lives as a trigger at the top of the rail, and the
workspace/user identity lives at the rail's foot. Row hover is a background
tint plus a pointer cursor; row selection (Messages) is a left accent border
plus a tinted background, the same visual grammar as the rail's own active
item — a single "this is the selected one" language reused everywhere.

## Responsive strategy

This first slice targets the desktop operating range procurement work
actually happens in (1280–1920px); the rail collapses to icons below ~1280px
before any table degrades. Full mobile adaptation is out of scope for this
prototype (see Deliberate exclusions) but the primitives (flex/grid, no
fixed pixel widths on containers) do not block it later.

## State and motion principles

Motion is feedback only: 120–160ms ease-out on hover/active/panel-resize,
nothing decorative, nothing on page load. Every list has an explicit empty
state (not just a blank area) and every async row (search progress, sending)
shows its state as text/badge, never a spinner standing in for information.

## Reference categories and synthesis

- **Attio** — dense, borderless record tables with restrained accent use;
  informed the Requests/Suppliers table grammar (hairlines, right-aligned
  metadata, no card wrapper).
- **Linear** — dark persistent rail with a light workspace, single accent,
  command-first search entry point; informed the App Shell.
- **Stripe Dashboard** — status/semantic color discipline (color always
  means something specific); informed the deadline/status badge system.
- **Superhuman** (Messages only) — full-width email-style message blocks
  instead of chat bubbles, keyboard-forward reading rhythm; informed the
  conversation pane.
- **GitHub/Sentry** — compact status/event iconography and badge shape;
  informed small status dots and count badges.

None of these products is reproduced; each contributed one specific
mechanism synthesized into SupplyDesk's own system above.

## Three signature decisions (recognizable without the logo)

1. A single left-accent-border language for "this is active/selected," used
   identically in the nav rail, table row focus, and the Messages
   navigator — one grammar, three places.
2. A four-state deadline vocabulary (overdue / today / soon / normal)
   rendered the same way everywhere a deadline appears (Dashboard, Requests).
3. ProcureSans reserved strictly for display-weight text, paired with Inter
   for everything dense — a deliberate two-typeface split most admin
   templates don't bother making.

## Deliberate exclusions

No gradients, no glassmorphism, no hero sections, no big illustrated empty
states, no card-per-record dashboards, no dark-mode-only aesthetic, no
top bar duplicate of the page header, no chat-bubble message rendering in
Messages, no full category-chip lists in the Suppliers table.

## Acceptance criteria for the first rendered slice

- The rail, page header and primary-action pattern are identical across all
  four screens.
- Requests and Suppliers render as dense single-line tables, not cards, at
  1440px.
- Dashboard is a grouped attention feed, not a KPI-tile wall.
- Messages shows the request → supplier → conversation model with one level
  of disclosure (not nested accordions) and email-style message blocks.
- Deadline urgency and status badges use only the semantic color ramp.
- No horizontal overflow at 1440px; ProcureSans and Inter both render
  (network/self-hosted fonts load, no FOUT to a generic fallback visible in
  a screenshot).
