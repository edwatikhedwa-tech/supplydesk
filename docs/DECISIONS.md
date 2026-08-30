# Decisions

## RESEND-001

Status: Confirmed by current SQLite implementation and tests.

Decision: Automatic initial-send protection is scoped to one workspace + request
+ normalized email.

Reason: The composite database guard prevents the same request/contact from
being created twice while allowing the same contact in another request or
workspace.

User impact: A repeated initial click for the same request/email is blocked.

Do not reinterpret as: This email can never be contacted again.

## RESEND-002

Status: Confirmed by current implementation and tests.

Decision: If the requested primary email was already used in the request and an
unambiguous NEVER_USED alternate exists in the same company card, one alternate
may be selected automatically.

Reason: It preserves one-contact-per-operation safety without silently sending
to every email on the card.

User impact: The effective recipient may differ from the visible primary; the
preflight result and queued target must show the same recipient.

Do not reinterpret as: All alternate emails should be sent automatically.

## RESEND-003

Status: Confirmed by current implementation and regression tests.

Decision: One company-card selection creates at most one outbound target/message
for the selected effective contact.

Reason: Company grouping must not turn one user action into multiple duplicate
messages.

User impact: Remaining company emails stay available as contact data and are not
automatically sent.

Do not reinterpret as: The UI already provides an explicit email picker.

## MAIL-001

Status: Confirmed by current UI labels, backend status mapping, and tests.

Decision: User-facing «Отправлено» represents SMTP/provider acceptance.

Reason: The application records a historical transport acceptance separately
from bounce, delivery-unknown, and Inbox evidence.

User impact: «Отправлено» means the sending server accepted the message.

Do not reinterpret as: The message is guaranteed to be delivered to the
recipient's Inbox.

## IDENTITY-001

Status: Confirmed by current grouping rules and tests.

Decision: Company cards may collapse rows only on confirmed global/legal identity;
same name alone is insufficient. Host/site rows remain distinct source contacts
unless the confirmed identity grouping says they belong to one company card.

Reason: A name can be shared by unrelated legal entities, while one company can
legitimately have multiple sites and emails.

User impact: A card can show multiple contacts; physical supplier rows are not
deleted by presentation grouping.

Do not reinterpret as: Every same-name or same-email row is safe to merge.

## DEPLOY-001

Status: Confirmed by current deployment configuration.

Decision: Local development supports SQLite; the intended Vercel production
path requires durable PostgreSQL through `DATABASE_URL`. SQLite under Vercel's
`/tmp` is only a fallback and is not durable production storage.

Reason: `vercel.json` excludes SQLite/mail-data and `api/index.py` documents the
production PostgreSQL requirement.

User impact: PostgreSQL acceptance is a release prerequisite for production
behavior, even though local SQLite acceptance is available.

Do not reinterpret as: PostgreSQL has already passed the current acceptance
suite.

## MAIL-SAFETY

Status: Confirmed by source inspection, isolated SQLite tests, mail/runtime
acceptance tests, and read-only live-state verification.

Decision: Outgoing mail is fail-closed. Default, missing, or invalid durable
state is disabled; enabling requires an explicit authenticated owner action with
CSRF protection and confirmation.

Reason: Application startup, imports, migrations, restarts, and malformed
configuration must never become implicit permission to contact suppliers.

User impact: Existing queued messages remain queued while outgoing is off. An
owner can deliberately change the global switch through
`POST /api/mail/runtime/outgoing`; the provider boundary still checks the
runtime and environment kill switch before transport.

Do not reinterpret as: Enabling the durable switch bypasses the production
runtime lock, the environment kill switch, account eligibility, or provider
delivery safeguards.
