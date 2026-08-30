-- postgres-only
--
-- global_supplier_finances.revenue/profit and global_supplier_finance_history's
-- same columns were declared INTEGER (migrations 009, 014) — Postgres's 32-bit
-- int, max ~2.1 billion. Real company revenue in rubles routinely exceeds that
-- (e.g. a mid-size ООО with 45 264 052 000 ₽ turnover), so Checko-sourced
-- values above ~2.1B were rejected outright on write. SQLite never enforced
-- the declared width (dynamic typing), so this only ever surfaced on Postgres.
--
-- Widening an existing column is not "purely additive" in the sense
-- migrations 009/014 describe, but there is no destructive alternative here:
-- the column already exists with the wrong width. ALTER COLUMN TYPE is safe
-- and idempotent (a no-op if already bigint) on Postgres. SQLite has no
-- equivalent syntax and doesn't need one (see MailRepository.ensure_schema,
-- which skips files starting with this "-- postgres-only" marker for SQLite).
ALTER TABLE global_supplier_finances ALTER COLUMN revenue TYPE BIGINT;
ALTER TABLE global_supplier_finances ALTER COLUMN profit TYPE BIGINT;
ALTER TABLE global_supplier_finance_history ALTER COLUMN revenue TYPE BIGINT;
ALTER TABLE global_supplier_finance_history ALTER COLUMN profit TYPE BIGINT;
