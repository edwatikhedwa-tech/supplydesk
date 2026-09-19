"""E2E replay v2 (EDW-38): the SAME 20 letters as scenarios.py, sent again on a fresh copy, against the behaviour the owner specified AFTER
the first E2E run. scenarios.py and the first report are not touched. This file is committed before any replay letter is sent.

What changed in the required behaviour (owner decisions, 2026-09-19):
  S01/S02/S10   'acknowledgement' / 'pending_quote' are decided by rules: no price, SKU, quantity or attachment -> 0 model calls, and they are not quotes
  S13           routing -> request resolution -> extraction: an unmatched letter with no price of its own is NOT analysed by a model before the request is resolved
  S11           a price in a letter of unknown request may be stored as an UNSCOPED SOURCE fact (provenance kept); a request-scoped fact is forbidden until the
                request is confirmed; the old expectation 'no fact at all' is replaced by 'no request-scoped fact' (recorded here, not silently)
  async         sync = fetch -> persist -> deduplicate -> enqueue; no analysis, no model call, no OCR inside sync; a worker does the rest
"""

from __future__ import annotations

import copy

from benchmarks.e2e_mail.scenarios import GLOBAL_EXPECT as V1_GLOBAL, SCENARIOS as V1

SCENARIOS = copy.deepcopy(V1)
for sc in SCENARIOS:
    ex = sc["expect"]
    if sc["id"] == "S01":
        ex.update(message_type="acknowledgement", body_ai_calls_max=0)
    if sc["id"] in ("S02", "S10"):
        ex.update(message_type="pending_quote", body_ai_calls_max=0)
    if sc["id"] == "S13":
        ex.update(body_ai_calls_max=0, message_type_not="quote")
    if sc["id"] == "S11":
        ex.update(body_facts=[500.0], body_fact_scope="source", request_scoped_facts=0)   # unscoped source fact allowed, request-scoped forbidden
    if ex["body_facts"] and sc["id"] != "S11":
        ex["body_fact_scope"] = "request"
    ex.setdefault("request_scoped_facts", len(ex["body_facts"]) if sc["request"] else 0)
    # body facts of S11 are plain prices in v2 (see above); the other scenarios keep (fragment, price) tuples
    if sc["id"] != "S11":
        ex["body_facts"] = list(ex["body_facts"])

GLOBAL_EXPECT = dict(
    V1_GLOBAL,
    scenarios=20,
    sync_runs_no_analysis=True,                 # right after sync: 0 rows in mail_analyses / mail_attachment_analyses, 0 model calls, 0 OCR
    jobs_enqueued_for_every_persisted_message=True,
    worker_finishes_all_jobs=True,
    duplicate_ai_calls=0,                       # no (workspace, request key) paid twice; replays are not paid
    duplicated_messages=0,                      # one object per Message-ID across mail_messages / mail_inbox_messages / mail_sent_messages
    duplicated_facts=0,                         # no two facts with the same (analysis, position); no fact set of one message stored twice
    sent_sync_A_new_objects=0,                  # A -> B: syncing A's Sent folder adds nothing for the RFQs
    sent_sync_B_new_objects=0,                  # B -> A: syncing B's Sent folder adds no second object and no phantom supplier for the replies
    max_total_cost_rub=1.0,
)
