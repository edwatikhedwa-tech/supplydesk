---
document_id: AUDIT-FUNCTIONAL-BASELINE-20260901
status: HISTORICAL
canonical: false
owner: audit
updated_at: 2026-09-01
source_commit: b5a454f9b39f3cbf01d640d5b67e4231ca25733a
---

# Functional baseline — audit workspace

## Status

**PARTIAL baseline.** Проверки выполнены в независимой audit-копии с
`SUPPLYDESK_ENV=development`, отдельной SQLite-копией и отключённой исходящей
почтой. Это фиксация текущего поведения, а не исправление продукта.

## Backend

Команда: `python -m pytest tests -vv --tb=short`. Набор `supplier_source_tests`
не запускался: он выполняет внешние read-only web lookups и не нужен для
локального regression baseline.

| Результат | Количество |
|---|---:|
| PASSED | 321 |
| FAILED | 52 |
| ERROR | 0 |
| SKIPPED | 1 |
| subtests passed | 4 |

Существующие FAIL сохранены как baseline; цель будущей очистки:
`NEW_FAILURES = 0`. Существенная часть падений ожидает fake-provider transport,
но этот прогон запускался с `MAIL_OUTGOING_DISABLED=1`; в этой задаче mail
провайдер не вызывался.

### Existing failed test IDs

`MailDeliverabilityAcceptanceTests`: `test_c14_resume_exposes_only_unsent_targets`,
`test_c15_resume_does_not_repeat_sent_job`, `test_c17_stop_remaining_does_not_change_sent`,
`test_c19_suppression_added_between_stages_is_applied_at_send`,
`test_c21_spam_policy_rejection_pauses_campaign`, `test_c22_auth_failure_pauses_campaign_and_account`,
`test_c23_transient_throttling_uses_existing_cooldown`,
`test_h1_operator_cap_holds_automatic_campaign_at_stage_two`,
`test_h2_without_operator_cap_preserves_automatic_stage_three`,
`test_h3_operator_cap_is_campaign_specific`, `test_h4_resume_does_not_bypass_active_operator_cap`,
`test_h5_removing_operator_cap_allows_normal_resume`, `test_h6_operator_cap_does_not_mutate_campaign_intent_or_snapshot`,
`test_m11_true_mode_pauses_after_completed_stage`, `test_m12_false_mode_advances_after_completed_stage`,
`test_r3_stage_review_resume_advances_only_after_completed_stage`,
`test_r5_manual_approval_still_requires_stage_review`,
`test_r6_automatic_rollout_still_advances_after_completed_stage`,
`test_stop_remaining_cancels_claim_released_after_stop`.

`MailIntegrationTests`: `test_explicit_html_contract_keeps_one_selected_company_to_one_message`,
`test_queue_creates_separate_thread_and_message_for_each_supplier`,
`test_reply_to_unmatched_inbox_message_sends_and_threads_without_a_supplier`,
`test_unmatched_inbox_reply_accepts_explicit_html_contract`.

`MailIntegrityTests`: `test_10_failed_gate_makes_no_provider_call`,
`test_10a_pre_data_encoding_failure_is_terminal_without_delivery_unknown`,
`test_11_success_then_result_db_failure_never_uses_ordinary_retry`,
`test_12_transport_error_after_transfer_is_unknown_without_retry`,
`test_14_status_transition_keeps_job_message_and_supplier_state_atomic`,
`test_17_sent_copy_failure_does_not_change_sent_status`,
`test_18_copy_is_attempted_after_result_write_failure`,
`test_19_sync_unmatched_reply_also_saves_sent_copy`,
`test_32_disabled_queue_does_not_spin_and_resumes_without_restart`,
`test_33_kill_switch_race_final_guard_blocks_provider_without_attempt_growth`,
`test_35_disabled_wait_preserves_retry_budget_for_real_transport_attempt`.

`MailPacingTests`: `test_continuation_job_can_run_while_source_campaign_is_paused`,
`test_p14_transient_refusal_uses_bounded_backoff`, `test_p16_permanent_refusal_is_terminal`,
`test_p17_uncertain_is_never_requeued`, `test_p18_auth_failure_opens_account_state`,
`test_p21_suppression_is_checked_after_queue_creation`, `test_p28_sync_reply_uses_same_reservation_table`,
`test_pace_w1_scheduled_not_before_is_a_hard_transport_lower_bound`,
`test_pace_w2_after_scheduled_time_can_start_transport`,
`test_pace_w3_kill_switch_during_wait_releases_without_smtp`,
`test_pace_w4_suppression_during_wait_is_checked_before_provider`,
`test_pace_w7_future_wait_uses_event_wait_without_busy_loop`,
`test_pace_w8_sequential_accepted_transports_respect_configured_interval`,
`test_pre_gate_provider_setup_failure_audits_no_irreversible_stage`,
`test_u6_known_transient_regression_still_retries_only_after_cooldown`,
`test_zr1_started_transient_is_consumed_and_cooldown_persists`,
`test_zr2_cooldown_blocks_new_reservation_not_zombie_reservation`,
`test_zr_reply_known_transient_closes_started_reservation`.

## Playwright / real HTTP

No route mocks were used for the acceptance checks below. No login, SMTP, real
email, production action, migration or destructive interaction was performed.

- Existing public shell test: **8/8 PASS** across configured desktop/mobile
  widths; no horizontal overflow; Axe violations empty.
- Audit live-route test: **18/18 PASS** for `/`, `/login`, `/requests`,
  `/suppliers`, `/messages` at 1440, 1024 and 390 widths.
- API smoke: `/api/auth/me` → 200, protected `/api/requests` → 401,
  `/api/does-not-exist` → 404.
- Screenshots: 15 files in `screenshots/live-routes/`; inspected desktop-wide
  and mobile-large home screenshots. No overlap, clipping or unreadable shell
  text was found in those inspected images.
- Audit server remains live at `http://127.0.0.1:18000`.
- The original source listener on port 8000 was observed during capture but was
  not listening at the final recheck; it was not stopped by this audit.

The existing live-email regression test failed before the content assertion:
the expected historical subject was not present in the copied current inbox.
Screenshot/trace are in `frontend/test-results/live-email-regression-*/`; the
flow is **NOT VERIFIED**, not a product defect proven by this run.

## Not verified

Authenticated supplier/request/mail actions, request-to-email linking, modal
mutations, HTML/plain rendering against a selected message, and safe fake-mail
send semantics were not fully accepted. These require suitable non-production
fixtures and a separate controlled test run.
