# Documentation map

Read-only map of Markdown files in the source tree. Vendor, build and analysis environments were excluded. No documentation was merged, renamed, deleted or edited in this audit.

## Canonical source and consistency result

`ai/CURRENT_STATE.md` is the only canonical current-state source, as declared by `AGENTS.md`, `ai/AI_CONTRACT.md`, `ai/WORKFLOW.md` and `docs/DOCUMENTATION_POLICY.md`. `docs/CURRENT_STATE.md` and `docs/DECISIONS.md` correctly carry historical/supporting markers. `Documents/28-8/**` documents inspected here link back to the canonical state.

Confirmed drift: `docs/CURRENT_STATE.md:24` still reports 493 supplier rows, while the independently checked frozen SQLite backup has 494 rows in `suppliers`. Because the source project is frozen/read-only for this task, this was recorded as a documentation conflict and not silently corrected.

Potentially confusing but not a runtime conflict: many root-level untracked reports and `Temp/**` copies repeat old task evidence without the canonical navigation header. They are classified conservatively as `ARCHIVE_CANDIDATE` or `UNKNOWN`; exact duplicates are not delete decisions.

State validator result: **FAIL** in the audit copy because one historical report
contains six absolute links to the original `<LOCAL_PATH>/Temp/` path. This is a
documentation portability issue, not evidence that the linked artifacts should
be deleted. The source was not edited.

## Per-document status

| document | status | git status | hash prefix | reason |
|---|---|---|---|---|
| `.agents/skills/neon/SKILL.md` | UNKNOWN | untracked | `e164a3e8b63ffc4c` | purpose/status requires owner review |
| `_archive/frontend-legacy/.superdesign/design-system.md` | UNKNOWN | untracked | `6e56f814edba7d94` | purpose/status requires owner review |
| `_archive/frontend-legacy/.superdesign/init/components.md` | UNKNOWN | untracked | `c063123529ed7793` | purpose/status requires owner review |
| `_archive/frontend-legacy/.superdesign/init/extractable-components.md` | UNKNOWN | untracked | `86aa8a81614b4952` | purpose/status requires owner review |
| `_archive/frontend-legacy/.superdesign/init/layouts.md` | UNKNOWN | untracked | `75e2d048eced64b7` | purpose/status requires owner review |
| `_archive/frontend-legacy/.superdesign/init/pages.md` | UNKNOWN | untracked | `7c30ce780d60767e` | purpose/status requires owner review |
| `_archive/frontend-legacy/.superdesign/init/routes.md` | UNKNOWN | untracked | `048c232692427118` | purpose/status requires owner review |
| `_archive/frontend-legacy/.superdesign/init/theme.md` | UNKNOWN | untracked | `8c489e656726ec60` | purpose/status requires owner review |
| `AGENTS.md` | CURRENT | tracked | `d0f91f1ca26e09d0` | repository entrypoint/instructions |
| `ai/ACTIVE_TASK.md` | CURRENT | tracked | `7cc4a450efb6a3bd` | current operating/state document under ai/ |
| `ai/adapters/CHATGPT_PROJECT_INSTRUCTIONS.md` | UNKNOWN | tracked | `357e2f3857d72af5` | purpose/status requires owner review |
| `ai/adapters/CLAUDE_PROJECT_INSTRUCTIONS.md` | UNKNOWN | tracked | `ced292cc36ee3e75` | purpose/status requires owner review |
| `ai/AI_CONTRACT.md` | CURRENT | tracked | `0320296485a7631a` | current operating/state document under ai/ |
| `ai/CHANGELOG.md` | CURRENT | tracked | `0d40f2f23f18553a` | current operating/state document under ai/ |
| `ai/CURRENT_STATE.md` | CURRENT | tracked | `c358c077280d28e1` | canonical current-state source |
| `ai/DECISIONS.md` | CURRENT | modified: M | `d878f3084ac08d9f` | current operating/state document under ai/ |
| `ai/DEFERRED_FINDINGS.md` | CURRENT | modified: M | `6f5adf4b9bf71c99` | current operating/state document under ai/ |
| `ai/INTERACTION_LOG.md` | CURRENT | tracked | `00f54cececa460fb` | current operating/state document under ai/ |
| `ai/LAST_HANDOFF.md` | CURRENT | tracked | `e750e3c286bc1097` | current operating/state document under ai/ |
| `ai/PUBLISH_ALLOWLIST.md` | UNKNOWN | tracked | `fa22710b56db0740` | purpose/status requires owner review |
| `ai/PUBLISH_DENYLIST.md` | UNKNOWN | tracked | `b582db28a7f14b92` | purpose/status requires owner review |
| `ai/PUBLISH_MANIFEST.md` | UNKNOWN | tracked | `a4a870b7b7edf137` | purpose/status requires owner review |
| `ai/PUBLISH_SECURITY_REPORT.md` | HISTORICAL | tracked | `965889d7c5c9a3df` | document marks itself historical/supporting |
| `ai/README.md` | CURRENT | tracked | `2912e1c68d87d2d5` | current operating/state document under ai/ |
| `ai/reports/TASK-COMMUNICATION-RULE-20260831-report.md` | HISTORICAL | tracked | `501587d596fe1f08` | dated task evidence/report |
| `ai/reports/TASK-DOCS-CANONICAL-20260901-report.md` | HISTORICAL | tracked | `5698dc84b2f2acc7` | dated task evidence/report |
| `ai/reports/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-report.md` | HISTORICAL | tracked | `f46a8b053ee7eaaa` | dated task evidence/report |
| `ai/reports/TASK-INSTRUCTION-CHECK-UX-20260901-report.md` | HISTORICAL | tracked | `af0b48a5f9d6626d` | dated task evidence/report |
| `ai/reports/TASK-MAIL-CONTENT-CONTRACT-AUDIT-20260830-report.md` | HISTORICAL | tracked | `2c690a17f2342cdc` | dated task evidence/report |
| `ai/reports/TASK-MAIL-CONTENT-CONTRACT-IMPLEMENTATION-20260831-report.md` | HISTORICAL | tracked | `fb0afc2e20034766` | dated task evidence/report |
| `ai/reports/TASK-MAIL-DELIVERY-UNKNOWN-VERIFY-20260831-report.md` | HISTORICAL | untracked | `d00231011c1fb8b3` | dated task evidence/report |
| `ai/reports/TASK-MAIL-DUPLICATE-GUARD-20260831-report.md` | HISTORICAL | untracked | `6ff1c5891aeacd1b` | dated task evidence/report |
| `ai/reports/TASK-MAIL-DUPLICATE-PROTECTION-FINAL-20260831-report.md` | HISTORICAL | tracked | `d17c9dee3c6c6f55` | dated task evidence/report |
| `ai/reports/TASK-MAIL-IDN-DELIVERY-CONTINUATION-FIX-20260831-report.md` | HISTORICAL | untracked | `2682d43178c87110` | dated task evidence/report |
| `ai/reports/TASK-MAIL-INCOMING-CONTINUATION-20260831-report.md` | HISTORICAL | tracked | `403f26589a546606` | dated task evidence/report |
| `ai/reports/TASK-MAIL-STATUS-RECONCILIATION-20260901-report.md` | HISTORICAL | tracked | `14059959184877e7` | dated task evidence/report |
| `ai/reports/TASK-MAILRU-FINAL-CONTINUATION-20260831-report.md` | HISTORICAL | tracked | `d8a0e198a96d141d` | dated task evidence/report |
| `ai/reports/TASK-MAILRU-REMAINING-CONTINUATION-20260831-report.md` | HISTORICAL | untracked | `7d8fbd39516d8928` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-AUDIT-20260831-report.md` | HISTORICAL | tracked | `87a5f4f4ee10feb6` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-AUDIT-REPAIR-20260831-report.md` | HISTORICAL | tracked | `c8e4592ac22e65a0` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-CID-HEIGHT-FIX-20260831-report.md` | HISTORICAL | tracked | `8d132bcd1487f794` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-NAV-DEFAULT-20260831-report.md` | HISTORICAL | tracked | `7839e8cee9cd09c6` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-NAV-TOGGLE-20260831-report.md` | HISTORICAL | tracked | `176b131713fe9222` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-PRIMARY-FILTER-20260831-report.md` | HISTORICAL | tracked | `26bd21c5908fd0a8` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-REAL-DATA-ACCEPTANCE-20260831-report.md` | HISTORICAL | tracked | `dc37cd7a43990768` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-STATUS-FILTER-20260831-report.md` | HISTORICAL | tracked | `cf619a2975ca3e32` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-UX-20260831-report.md` | HISTORICAL | tracked | `da57f0d3ca4eaa4e` | dated task evidence/report |
| `ai/reports/TASK-MESSAGES-UX-FIX-20260831-report.md` | HISTORICAL | tracked | `15e271dc7c721be0` | dated task evidence/report |
| `ai/reports/TASK-PROJECT-RECOVERY-20260831-report.md` | HISTORICAL | untracked | `ccfcab5cfd1b3259` | dated task evidence/report |
| `ai/reports/TASK-PUBLISH-SAFETY-001-report.md` | HISTORICAL | tracked | `75fb9bfea0d0f023` | dated task evidence/report |
| `ai/reports/TASK-REMOTE-REPOSITORY-PREPARATION-report.md` | HISTORICAL | tracked | `7eceb756c672e1a6` | dated task evidence/report |
| `ai/reports/TASK-REMOTE-SETUP-SIMPLIFIED-report.md` | HISTORICAL | tracked | `24e476a7fee2b8c5` | dated task evidence/report |
| `ai/reports/TASK-SERVER-START-20260831-report.md` | HISTORICAL | tracked | `b4d1a44ba4e040aa` | dated task evidence/report |
| `ai/reports/TASK-STATE-CLOSEOUT-20260830-report.md` | HISTORICAL | tracked | `e6b9970b31e87393` | dated task evidence/report |
| `ai/reports/TASK-STATE-CONTROL-20260830-AUDIT.md` | HISTORICAL | tracked | `524110bea9436076` | dated task evidence/report |
| `ai/reports/TASK-STATE-CONTROL-20260830-FINAL.md` | HISTORICAL | tracked | `f0593f31e34be067` | dated task evidence/report |
| `ai/reports/TASK-STATE-POST-PUBLISH-RECONCILIATION-20260830-report.md` | HISTORICAL | tracked | `0426c6e66c192bf1` | dated task evidence/report |
| `ai/reports/TASK-STATE-RECONCILIATION-report.md` | HISTORICAL | tracked | `8997f6798e5a1e26` | dated task evidence/report |
| `ai/reports/TASK-SYSTEM-FRONT-AUDIT-20260901-report.md` | HISTORICAL | tracked | `e883c5d8af9a3d9d` | dated task evidence/report |
| `ai/templates/ACCEPTANCE_TEMPLATE.md` | UNKNOWN | tracked | `4fbbf29e68736a32` | purpose/status requires owner review |
| `ai/templates/TASK_TEMPLATE.md` | ARCHIVE_CANDIDATE | tracked | `5ac4994fa999ab6b` | report-like or dated artifact without canonical-state role |
| `ai/WORKFLOW.md` | CURRENT | tracked | `ae0d64e781b90bc2` | current operating/state document under ai/ |
| `CAMPAIGN_130_LIVE_RESULT.md` | ARCHIVE_CANDIDATE | untracked | `c55b2455dc644e8a` | report-like or dated artifact without canonical-state role |
| `CAMPAIGN_HEALTH_CORRECTIVE_LIVE_RESULT.md` | HISTORICAL | untracked | `56d88a2e4a647bd6` | document marks itself historical/supporting |
| `CLAUDE.md` | CURRENT | tracked | `c5fc1381401b6ce2` | repository entrypoint/instructions |
| `docs/CURRENT_STATE.md` | HISTORICAL | tracked | `c313d715845c6707` | document marks itself historical/supporting |
| `docs/DECISIONS.md` | HISTORICAL | tracked | `f4a413a92f70fd85` | document marks itself historical/supporting |
| `docs/DOCUMENTATION_POLICY.md` | UNKNOWN | tracked | `9e37568fa80abeed` | supporting tree without a current-state role proven by the file header |
| `docs/ENGINEERING_CONTRACT.md` | UNKNOWN | tracked | `eb3d95bb6b70b436` | supporting tree without a current-state role proven by the file header |
| `docs/WORK_LOG.md` | HISTORICAL | tracked | `f550e67cc81bea80` | document marks itself historical/supporting |
| `Documents/28-8/dashboard-recommendations.md` | HISTORICAL | tracked | `592f7b02590b14de` | document marks itself historical/supporting |
| `Documents/28-8/DESIGN.md` | HISTORICAL | tracked | `dbbd041dfca8bc87` | document marks itself historical/supporting |
| `Documents/28-8/enrichment-and-cache.md` | HISTORICAL | tracked | `83786b114d0c17c9` | document marks itself historical/supporting |
| `Documents/28-8/FRONTEND_QA.md` | HISTORICAL | tracked | `a5133a491c1e29aa` | document marks itself historical/supporting |
| `Documents/28-8/INDEX.md` | HISTORICAL | tracked | `d57762b3e0fcd8ab` | document marks itself historical/supporting |
| `Documents/28-8/mail-integration.md` | HISTORICAL | tracked | `158b231afb8b45f6` | document marks itself historical/supporting |
| `Documents/28-8/mailru-live-acceptance-reconciliation-20260829.md` | HISTORICAL | tracked | `43f7eb2661cb0cf1` | document marks itself historical/supporting |
| `Documents/28-8/messages-and-mail-audit.md` | HISTORICAL | tracked | `6fb9b4154c89bbf4` | document marks itself historical/supporting |
| `Documents/28-8/PROJECT_DOCUMENTATION.md` | HISTORICAL | tracked | `f5900d8710dd124a` | document marks itself historical/supporting |
| `Documents/28-8/PROJECT_STATUS.md` | HISTORICAL | tracked | `388b79067ae57c26` | document marks itself historical/supporting |
| `Documents/28-8/README.md` | HISTORICAL | tracked | `8df65fe82d8965af` | document marks itself historical/supporting |
| `Documents/28-8/requests-page-audit.md` | HISTORICAL | tracked | `27ecdb34e48fead8` | document marks itself historical/supporting |
| `Documents/28-8/suppliers-screen.md` | HISTORICAL | tracked | `af52e2a1d2d95f15` | document marks itself historical/supporting |
| `EMAIL_CAMPAIGN_UI_ITERATION4.md` | UNKNOWN | untracked | `1433edb15ae58c29` | purpose/status requires owner review |
| `EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md` | ARCHIVE_CANDIDATE | untracked | `34ec4b84e9e6e668` | report-like or dated artifact without canonical-state role |
| `EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md` | DUPLICATE | untracked | `b4d18013f77556fb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `EMAIL_DELIVERABILITY_ITERATION3.md` | ARCHIVE_CANDIDATE | untracked | `dc49f3c1c16351c8` | report-like or dated artifact without canonical-state role |
| `EMAIL_DELIVERABILITY_ITERATION3_FINAL_REVIEW.md` | DUPLICATE | untracked | `dc2fc426e6496fb3` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md` | DUPLICATE | untracked | `5d4bff139e5f34d2` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `EMAIL_DELIVERABILITY_ITERATION3_REPORT.md` | ARCHIVE_CANDIDATE | untracked | `d416a8ab84d9c4e1` | report-like or dated artifact without canonical-state role |
| `EMAIL_DELIVERABILITY_ITERATION3_STEP0.md` | DUPLICATE | untracked | `530b0b68ac4e7c0a` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `EMAIL_DELIVERABILITY_ITERATION3_UI_GAP.md` | DUPLICATE | untracked | `1651c17a841b656e` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `EMAIL_INTEGRITY_ITERATION1_REPORT.md` | ARCHIVE_CANDIDATE | untracked | `780d8fe721a37ed4` | report-like or dated artifact without canonical-state role |
| `EMAIL_INTEGRITY_STEP0_REPORT.md` | ARCHIVE_CANDIDATE | untracked | `939fcc1f4dbf9b8a` | report-like or dated artifact without canonical-state role |
| `EMAIL_PACING_ITERATION2.md` | UNKNOWN | untracked | `4638b60827eedf00` | purpose/status requires owner review |
| `EMAIL_PACING_ITERATION2_P0_CORRECTIVE_REPORT.md` | DUPLICATE | untracked | `e0a36a2aeb365837` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `EMAIL_PACING_ITERATION2_REPORT.md` | ARCHIVE_CANDIDATE | untracked | `a5fb76209e8ce736` | report-like or dated artifact without canonical-state role |
| `EMAIL_PACING_ITERATION2_STEP0.md` | UNKNOWN | untracked | `b65b85c7621cebc6` | purpose/status requires owner review |
| `frontend/artifacts/storybook-playwright-report/data/031d33050b2d76ec99c07acd6674c0cb7d153cba.md` | UNKNOWN | ignored | `42d84fecfb94f21b` | purpose/status requires owner review |
| `frontend/artifacts/storybook-playwright-report/data/08b7804b53a7b04775f915bba391f1f2575c9341.md` | UNKNOWN | ignored | `c59e20752e2d671e` | purpose/status requires owner review |
| `frontend/artifacts/storybook-playwright-report/data/3d131953d69a3b4ed2b1f2d8fd4dfe39163b0189.md` | UNKNOWN | ignored | `dc8ec54544a1931a` | purpose/status requires owner review |
| `frontend/artifacts/storybook-playwright-report/data/f07950ed0b605b1c7bf544e2b42c7b5bb6de554f.md` | UNKNOWN | ignored | `febc21d8bc599be6` | purpose/status requires owner review |
| `JOB46_CONTROLLED_RETRY_AFTER.md` | HISTORICAL | untracked | `0e7ce5d18136fdab` | document marks itself historical/supporting |
| `JOB46_CONTROLLED_RETRY_BEFORE.md` | HISTORICAL | untracked | `4c4004a174e69b46` | document marks itself historical/supporting |
| `P0_REVIEW_EXPORT/00_README.md` | DUPLICATE | untracked | `04f80918c5364ac8` | purpose/status requires owner review; exact duplicate group is recorded below |
| `P0_REVIEW_EXPORT/EMAIL_PACING_ITERATION2_P0_CORRECTIVE_REPORT.md` | DUPLICATE | untracked | `e0a36a2aeb365837` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `P0_REVIEW_EXPORT/FILE_MANIFEST.md` | DUPLICATE | untracked | `23a5d10cad91657e` | purpose/status requires owner review; exact duplicate group is recorded below |
| `P0_REVIEW_EXPORT/P0_LIVE_STATE_SNAPSHOT.md` | DUPLICATE | untracked | `6b22d1f4d403b847` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `P0_REVIEW_VERIFY/00_README.md` | DUPLICATE | untracked | `04f80918c5364ac8` | purpose/status requires owner review; exact duplicate group is recorded below |
| `P0_REVIEW_VERIFY/EMAIL_PACING_ITERATION2_P0_CORRECTIVE_REPORT.md` | DUPLICATE | untracked | `e0a36a2aeb365837` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `P0_REVIEW_VERIFY/FILE_MANIFEST.md` | DUPLICATE | untracked | `23a5d10cad91657e` | purpose/status requires owner review; exact duplicate group is recorded below |
| `P0_REVIEW_VERIFY/P0_LIVE_STATE_SNAPSHOT.md` | DUPLICATE | untracked | `6b22d1f4d403b847` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_EXPORT/00_README.md` | DUPLICATE | untracked | `a90d513e412f01de` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md` | DUPLICATE | untracked | `ffcd19ab4130d7bb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md` | DUPLICATE | untracked | `b0a941bd6354c9dc` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_EXPORT/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md` | DUPLICATE | untracked | `bdfcd69adcef84ef` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_EXPORT/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md` | DUPLICATE | untracked | `71c052075eab4d3f` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_EXPORT/01_DOCUMENTATION/mail-integration.md` | DUPLICATE | untracked | `24d3a9e4449a4096` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT/01_DOCUMENTATION/messages-and-mail-audit.md` | DUPLICATE | untracked | `37d475b995abab67` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md` | DUPLICATE | untracked | `d099680c05d6f7f9` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT/01_DOCUMENTATION/PROJECT_STATUS.md` | DUPLICATE | untracked | `952f48c6418db1e7` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_EXPORT/FILE_MANIFEST.md` | DUPLICATE | untracked | `a4552d6d6d4b726f` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT/FINAL_REVIEW_SUMMARY.md` | DUPLICATE | untracked | `6660edc80eae65b2` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/00_README.md` | DUPLICATE | untracked | `a90d513e412f01de` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md` | DUPLICATE | untracked | `ffcd19ab4130d7bb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md` | DUPLICATE | untracked | `b0a941bd6354c9dc` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md` | DUPLICATE | untracked | `bdfcd69adcef84ef` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md` | DUPLICATE | untracked | `71c052075eab4d3f` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/mail-integration.md` | DUPLICATE | untracked | `24d3a9e4449a4096` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/messages-and-mail-audit.md` | DUPLICATE | untracked | `37d475b995abab67` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md` | DUPLICATE | untracked | `d099680c05d6f7f9` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/PROJECT_STATUS.md` | DUPLICATE | untracked | `952f48c6418db1e7` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/FILE_MANIFEST.md` | DUPLICATE | untracked | `a4552d6d6d4b726f` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_EXPORT_VERIFY/FINAL_REVIEW_SUMMARY.md` | DUPLICATE | untracked | `6660edc80eae65b2` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4/00_README.md` | HISTORICAL | untracked | `51a83cfd4b2a1bb1` | document marks itself historical/supporting |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md` | UNKNOWN | untracked | `2486c0c04c6bee34` | purpose/status requires owner review |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md` | ARCHIVE_CANDIDATE | untracked | `6b966b79f0559488` | report-like or dated artifact without canonical-state role |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md` | DUPLICATE | untracked | `b4d18013f77556fb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md` | DUPLICATE | untracked | `bdfcd69adcef84ef` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md` | DUPLICATE | untracked | `5d4bff139e5f34d2` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md` | DUPLICATE | untracked | `71c052075eab4d3f` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_STEP0.md` | DUPLICATE | untracked | `530b0b68ac4e7c0a` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/mail-integration.md` | UNKNOWN | untracked | `cd38706f578bf637` | purpose/status requires owner review |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/messages-and-mail-audit.md` | UNKNOWN | untracked | `97d4b08ffeb95c37` | purpose/status requires owner review |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md` | UNKNOWN | untracked | `a8bc13426824d7f1` | purpose/status requires owner review |
| `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/PROJECT_STATUS.md` | ARCHIVE_CANDIDATE | untracked | `41cf335035fd6639` | report-like or dated artifact without canonical-state role |
| `REVIEW_PACKAGE_ITERATION4/06_CONTEXT/CURRENT_GAP.md` | UNKNOWN | untracked | `853a5d75e58dae24` | purpose/status requires owner review |
| `REVIEW_PACKAGE_ITERATION4/FILE_MANIFEST.md` | UNKNOWN | untracked | `a087500fc61c0a39` | purpose/status requires owner review |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/00_README.md` | HISTORICAL | untracked | `7e8f1d8eaf27bd29` | document marks itself historical/supporting |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md` | DUPLICATE | untracked | `ffcd19ab4130d7bb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md` | DUPLICATE | untracked | `b0a941bd6354c9dc` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md` | DUPLICATE | untracked | `b4d18013f77556fb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md` | DUPLICATE | untracked | `bdfcd69adcef84ef` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_FINAL_REVIEW.md` | DUPLICATE | untracked | `dc2fc426e6496fb3` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md` | DUPLICATE | untracked | `5d4bff139e5f34d2` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md` | DUPLICATE | untracked | `71c052075eab4d3f` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_STEP0.md` | DUPLICATE | untracked | `530b0b68ac4e7c0a` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_UI_GAP.md` | DUPLICATE | untracked | `1651c17a841b656e` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/mail-integration.md` | DUPLICATE | untracked | `24d3a9e4449a4096` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/messages-and-mail-audit.md` | DUPLICATE | untracked | `46ec439b17337e97` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md` | DUPLICATE | untracked | `4e878d2fd5d88455` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/PROJECT_STATUS.md` | DUPLICATE | untracked | `952f48c6418db1e7` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/FILE_MANIFEST.md` | UNKNOWN | untracked | `89d2fcf7a4417010` | purpose/status requires owner review |
| `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/FINAL_REVIEW_SUMMARY.md` | UNKNOWN | untracked | `8a646231f214b5e4` | purpose/status requires owner review |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/00_README.md` | DUPLICATE | untracked | `2641060fac6471df` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md` | DUPLICATE | untracked | `ffcd19ab4130d7bb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md` | DUPLICATE | untracked | `b0a941bd6354c9dc` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md` | DUPLICATE | untracked | `b4d18013f77556fb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md` | DUPLICATE | untracked | `bdfcd69adcef84ef` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md` | DUPLICATE | untracked | `5d4bff139e5f34d2` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md` | DUPLICATE | untracked | `71c052075eab4d3f` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_STEP0.md` | DUPLICATE | untracked | `530b0b68ac4e7c0a` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/mail-integration.md` | DUPLICATE | untracked | `24d3a9e4449a4096` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/messages-and-mail-audit.md` | DUPLICATE | untracked | `46ec439b17337e97` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md` | DUPLICATE | untracked | `4e878d2fd5d88455` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/PROJECT_STATUS.md` | DUPLICATE | untracked | `952f48c6418db1e7` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/FILE_MANIFEST.md` | DUPLICATE | untracked | `2665620e866a728a` | purpose/status requires owner review; exact duplicate group is recorded below |
| `REVIEW_PACKAGE_ITERATION4_FINAL_V2/FINAL_REVIEW_SUMMARY.md` | DUPLICATE | untracked | `51e2aec5c60fa2d1` | purpose/status requires owner review; exact duplicate group is recorded below |
| `SMTP_EVIDENCE_CONTROLLED_LIVE_BEFORE.md` | HISTORICAL | untracked | `36d843d60ac173a5` | document marks itself historical/supporting |
| `SMTP_EVIDENCE_CONTROLLED_LIVE_REPORT.md` | HISTORICAL | untracked | `08e402f47551f804` | document marks itself historical/supporting |
| `STAGE2_CONTROLLED_LIVE_AFTER.md` | ARCHIVE_CANDIDATE | untracked | `c0ac4cf904eacc53` | report-like or dated artifact without canonical-state role |
| `STAGE2_CONTROLLED_LIVE_BEFORE.md` | ARCHIVE_CANDIDATE | untracked | `16376850a0b8072a` | report-like or dated artifact without canonical-state role |
| `STAGE2_LIVE_RESUME_BEFORE.md` | ARCHIVE_CANDIDATE | untracked | `dc198c2526744cf3` | report-like or dated artifact without canonical-state role |
| `STAGE2_OPERATOR_HOLD_READY.md` | UNKNOWN | untracked | `39ced199f31abf94` | purpose/status requires owner review |
| `supplier_discovery_v2/BENCHMARK.md` | UNKNOWN | tracked | `8cb2438534a09080` | purpose/status requires owner review |
| `supplier_discovery_v2/out/latest_summary.md` | UNKNOWN | ignored | `981e9a7cc503a804` | purpose/status requires owner review |
| `supplier_discovery_v2/README.md` | UNKNOWN | tracked | `b173a85c50ea18f3` | purpose/status requires owner review |
| `supplier_source_tests/out/latest_summary.md` | UNKNOWN | untracked | `dced9d861667b593` | purpose/status requires owner review |
| `supplier_source_tests/README.md` | UNKNOWN | untracked | `d8d3c8e754dc5d2d` | purpose/status requires owner review |
| `supplier_source_tests/SOURCE_MATRIX.md` | UNKNOWN | untracked | `3b56f331fae20d48` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/AGENTS.md` | UNKNOWN | untracked | `e19f4a95beac0380` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/ai__ACTIVE_TASK.md` | ARCHIVE_CANDIDATE | untracked | `c8803783e361c487` | report-like or dated artifact without canonical-state role |
| `Temp/20260901-docs-canonical/ai__AI_CONTRACT.md` | UNKNOWN | untracked | `8ce130170e08084a` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/ai__CHANGELOG.md` | UNKNOWN | untracked | `e7bd265dff8b55b1` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/ai__CURRENT_STATE.md` | HISTORICAL | untracked | `6672ca66e63ec5ba` | document marks itself historical/supporting |
| `Temp/20260901-docs-canonical/ai__DECISIONS.md` | UNKNOWN | untracked | `ba019f67a8ccd5e3` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/ai__DEFERRED_FINDINGS.md` | HISTORICAL | untracked | `4eb50ca068eb510c` | document marks itself historical/supporting |
| `Temp/20260901-docs-canonical/ai__INTERACTION_LOG.md` | UNKNOWN | untracked | `454d7a6d9a586020` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/ai__LAST_HANDOFF.md` | ARCHIVE_CANDIDATE | untracked | `0c32a36460a48a4e` | report-like or dated artifact without canonical-state role |
| `Temp/20260901-docs-canonical/ai__WORKFLOW.md` | UNKNOWN | untracked | `077700ab7afb2e6d` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/docs__CURRENT_STATE.md` | UNKNOWN | untracked | `d14e4ccecec9b0bf` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/docs__DECISIONS.md` | UNKNOWN | untracked | `a362ddaa8a98be38` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/docs__ENGINEERING_CONTRACT.md` | UNKNOWN | untracked | `7d2ba10e5837d5b9` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/docs__WORK_LOG.md` | HISTORICAL | untracked | `f0bd80c2d62faba9` | document marks itself historical/supporting |
| `Temp/20260901-docs-canonical/Documents__28-8__FRONTEND_QA.md` | UNKNOWN | untracked | `2ddd248835ac866f` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/Documents__28-8__INDEX.md` | UNKNOWN | untracked | `de361c926478ecd3` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/Documents__28-8__mail-integration.md` | UNKNOWN | untracked | `ec237e1246efab3a` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/Documents__28-8__messages-and-mail-audit.md` | UNKNOWN | untracked | `acb1c0ab44587fc5` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/Documents__28-8__PROJECT_DOCUMENTATION.md` | UNKNOWN | untracked | `39a0a82a44cff099` | purpose/status requires owner review |
| `Temp/20260901-docs-canonical/Documents__28-8__PROJECT_STATUS.md` | ARCHIVE_CANDIDATE | untracked | `13f8b98b42e32265` | report-like or dated artifact without canonical-state role |
| `Temp/20260901-docs-canonical/Documents__28-8__README.md` | UNKNOWN | untracked | `7dce495cfe42010a` | purpose/status requires owner review |
| `Temp/20260901-system-front-audit/ACTIVE_TASK.md` | HISTORICAL | untracked | `5fd4ccc747a814c4` | document marks itself historical/supporting |
| `Temp/20260901-system-front-audit/CHANGELOG.md` | HISTORICAL | untracked | `1c4f3276eda988af` | document marks itself historical/supporting |
| `Temp/20260901-system-front-audit/CURRENT_STATE.md` | HISTORICAL | untracked | `875290b18db9e516` | document marks itself historical/supporting |
| `Temp/20260901-system-front-audit/DEFERRED_FINDINGS.md` | HISTORICAL | untracked | `74844caf54b63d8f` | document marks itself historical/supporting |
| `Temp/20260901-system-front-audit/INTERACTION_LOG.md` | UNKNOWN | untracked | `80fa3e4f58036b6c` | purpose/status requires owner review |
| `Temp/20260901-system-front-audit/LAST_HANDOFF.md` | ARCHIVE_CANDIDATE | untracked | `a6ea206deeff882b` | report-like or dated artifact without canonical-state role |
| `Temp/acceptance_20260829_campaign1059/AUDIT.md` | UNKNOWN | untracked | `d92d67e705f6bf0a` | purpose/status requires owner review |
| `Temp/agent-state-control-backup-20260830/CLAUDE.md` | UNKNOWN | untracked | `bc83cdb79c478558` | purpose/status requires owner review |
| `Temp/instructions-backup-20260831-recommendation-language/AGENTS.before-recommendation-language.md` | ARCHIVE_CANDIDATE | untracked | `14210058e7c0ae85` | report-like or dated artifact without canonical-state role |
| `Temp/instructions-backup-20260831-recommendation-language/AI_CONTRACT.before-recommendation-language.md` | ARCHIVE_CANDIDATE | untracked | `35b3780f2b3f790b` | report-like or dated artifact without canonical-state role |
| `Temp/instructions-backup-20260831/AGENTS.md` | UNKNOWN | untracked | `3b97288a4d1a21ed` | purpose/status requires owner review |
| `Temp/instructions-backup-20260831/AI_CONTRACT.md` | UNKNOWN | untracked | `e560a9716e3e7a6c` | purpose/status requires owner review |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/00_README.md` | DUPLICATE | untracked | `2641060fac6471df` | purpose/status requires owner review; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md` | DUPLICATE | untracked | `ffcd19ab4130d7bb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md` | DUPLICATE | untracked | `b0a941bd6354c9dc` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md` | DUPLICATE | untracked | `b4d18013f77556fb` | purpose/status requires owner review; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md` | DUPLICATE | untracked | `bdfcd69adcef84ef` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md` | DUPLICATE | untracked | `5d4bff139e5f34d2` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md` | DUPLICATE | untracked | `71c052075eab4d3f` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_STEP0.md` | DUPLICATE | untracked | `530b0b68ac4e7c0a` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/mail-integration.md` | DUPLICATE | untracked | `24d3a9e4449a4096` | purpose/status requires owner review; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/messages-and-mail-audit.md` | DUPLICATE | untracked | `46ec439b17337e97` | purpose/status requires owner review; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md` | DUPLICATE | untracked | `4e878d2fd5d88455` | purpose/status requires owner review; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/PROJECT_STATUS.md` | DUPLICATE | untracked | `952f48c6418db1e7` | report-like or dated artifact without canonical-state role; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/FILE_MANIFEST.md` | DUPLICATE | untracked | `2665620e866a728a` | purpose/status requires owner review; exact duplicate group is recorded below |
| `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/FINAL_REVIEW_SUMMARY.md` | DUPLICATE | untracked | `51e2aec5c60fa2d1` | purpose/status requires owner review; exact duplicate group is recorded below |
| `Temp/state-backup-20260831-messages-audit/CHANGELOG.md` | UNKNOWN | untracked | `99efd07346feb56e` | purpose/status requires owner review |
| `Temp/state-backup-20260831-messages-audit/CURRENT_STATE.md` | UNKNOWN | untracked | `bf59d746eb1f4eb3` | purpose/status requires owner review |
| `Temp/state-backup-20260831-messages-audit/INTERACTION_LOG.md` | UNKNOWN | untracked | `b38de91339fb32a2` | purpose/status requires owner review |
| `Temp/state-backup-20260831-messages-audit/LAST_HANDOFF.md` | ARCHIVE_CANDIDATE | untracked | `bf28dda7c90d2a78` | report-like or dated artifact without canonical-state role |
| `Temp/state-backup-20260831-messages-implementation-ACTIVE_TASK.md` | ARCHIVE_CANDIDATE | untracked | `89000847c3e5ce91` | report-like or dated artifact without canonical-state role |
| `Temp/state-backup-20260831-messages-implementation-closeout/ACTIVE_TASK.md` | ARCHIVE_CANDIDATE | untracked | `bd104281b869b1bc` | report-like or dated artifact without canonical-state role |
| `Temp/state-backup-20260831-messages-implementation-closeout/CHANGELOG.md` | UNKNOWN | untracked | `4be334b8af110e43` | purpose/status requires owner review |
| `Temp/state-backup-20260831-messages-implementation-closeout/CURRENT_STATE.md` | UNKNOWN | untracked | `ca39b1c655811a4e` | purpose/status requires owner review |
| `Temp/state-backup-20260831-messages-implementation-closeout/DECISIONS.md` | UNKNOWN | untracked | `231491761ff5851b` | purpose/status requires owner review |
| `Temp/state-backup-20260831-messages-implementation-closeout/DEFERRED_FINDINGS.md` | HISTORICAL | untracked | `1dfed8512303a791` | document marks itself historical/supporting |
| `Temp/state-backup-20260831-messages-implementation-closeout/INTERACTION_LOG.md` | UNKNOWN | untracked | `9d22a3c89a85d0e5` | purpose/status requires owner review |
| `Temp/state-backup-20260831-messages-implementation-closeout/LAST_HANDOFF.md` | ARCHIVE_CANDIDATE | untracked | `e559bdc895d1e1f0` | report-like or dated artifact without canonical-state role |
| `Temp/state-backup-20260831-server-start/ACTIVE_TASK.md` | HISTORICAL | untracked | `c525f73a89942c62` | document marks itself historical/supporting |
| `Temp/state-backup-20260831-server-start/CHANGELOG.md` | UNKNOWN | untracked | `64a651fd249e05a8` | purpose/status requires owner review |
| `Temp/state-backup-20260831-server-start/CURRENT_STATE.md` | UNKNOWN | untracked | `b3e439a8ceaf3a50` | purpose/status requires owner review |
| `Temp/state-backup-20260831-server-start/INTERACTION_LOG.md` | UNKNOWN | untracked | `5d3f06bd33bbcbf7` | purpose/status requires owner review |
| `Temp/state-backup-20260831-server-start/LAST_HANDOFF.md` | ARCHIVE_CANDIDATE | untracked | `ad4a4985335ec9af` | report-like or dated artifact without canonical-state role |
| `Temp/state-backup-20260831-server-start/TASK-PROJECT-RECOVERY-20260831-report.md` | ARCHIVE_CANDIDATE | untracked | `4795820d4f2df7ea` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups-TASK-MAIL-STATUS-RECONCILIATION-20260901-20260901-055358/ACTIVE_TASK.md` | HISTORICAL | untracked | `9d4f37334796ff9e` | document marks itself historical/supporting |
| `Temp/state-backups-TASK-MAIL-STATUS-RECONCILIATION-20260901-20260901-055358/CHANGELOG.md` | HISTORICAL | untracked | `1667dc4f5174790e` | document marks itself historical/supporting |
| `Temp/state-backups-TASK-MAIL-STATUS-RECONCILIATION-20260901-20260901-055358/INTERACTION_LOG.md` | HISTORICAL | untracked | `96960a6dd43b5ece` | document marks itself historical/supporting |
| `Temp/state-backups-TASK-MAILRU-FINAL-CONTINUATION-20260831/ACTIVE_TASK.before.md` | ARCHIVE_CANDIDATE | untracked | `31ece62d06a4cef3` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups-TASK-MAILRU-FINAL-CONTINUATION-20260831/CHANGELOG.before.md` | ARCHIVE_CANDIDATE | untracked | `2ed21e13b06304bf` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups-TASK-MAILRU-FINAL-CONTINUATION-20260831/INTERACTION_LOG.before.md` | ARCHIVE_CANDIDATE | untracked | `6ceed85843f2135c` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-1752/ACTIVE_TASK.md` | ARCHIVE_CANDIDATE | untracked | `f10e5de86e71ac69` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-1752/CHANGELOG.md` | UNKNOWN | untracked | `7fee278ac77a64b8` | purpose/status requires owner review |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-1752/CURRENT_STATE.md` | UNKNOWN | untracked | `9dadc29b2db11550` | purpose/status requires owner review |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-1752/INTERACTION_LOG.md` | UNKNOWN | untracked | `9f5d852378ffc60f` | purpose/status requires owner review |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-1752/LAST_HANDOFF.md` | ARCHIVE_CANDIDATE | untracked | `99a8322e1110ef0a` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-send-closeout/ACTIVE_TASK.md` | ARCHIVE_CANDIDATE | untracked | `23d351d441c5400c` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-send-closeout/CHANGELOG.md` | UNKNOWN | untracked | `a9e9065bdd9a88cf` | purpose/status requires owner review |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-send-closeout/CURRENT_STATE.md` | UNKNOWN | untracked | `1c0120338a5cbd72` | purpose/status requires owner review |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-send-closeout/INTERACTION_LOG.md` | UNKNOWN | untracked | `5bad44724745af80` | purpose/status requires owner review |
| `Temp/state-backups/TASK-FRONTEND-MAILRU-CONTINUATION-20260831-send-closeout/LAST_HANDOFF.md` | ARCHIVE_CANDIDATE | untracked | `5e873b566f942bc1` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups/TASK-MESSAGES-PRIMARY-FILTER-20260831/ACTIVE_TASK.md` | ARCHIVE_CANDIDATE | untracked | `f0e4bb1a08fff30a` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups/TASK-MESSAGES-PRIMARY-FILTER-20260831/CHANGELOG.md` | UNKNOWN | untracked | `d36af8a92e6b8895` | purpose/status requires owner review |
| `Temp/state-backups/TASK-MESSAGES-PRIMARY-FILTER-20260831/CURRENT_STATE.md` | UNKNOWN | untracked | `8509e8b74a79b507` | purpose/status requires owner review |
| `Temp/state-backups/TASK-MESSAGES-PRIMARY-FILTER-20260831/INTERACTION_LOG.md` | UNKNOWN | untracked | `7e0b1401bee7a340` | purpose/status requires owner review |
| `Temp/state-backups/TASK-MESSAGES-PRIMARY-FILTER-20260831/LAST_HANDOFF.md` | ARCHIVE_CANDIDATE | untracked | `8fb0e426bbc2b0c0` | report-like or dated artifact without canonical-state role |
| `Temp/state-backups/TASK-SERVER-START-20260831/CHANGELOG.md` | UNKNOWN | untracked | `3f95bfe195e98430` | purpose/status requires owner review |
| `Temp/state-backups/TASK-SERVER-START-20260831/CURRENT_STATE.md` | UNKNOWN | untracked | `4ec18197ffb46d0d` | purpose/status requires owner review |
| `Temp/state-backups/TASK-SERVER-START-20260831/INTERACTION_LOG.md` | UNKNOWN | untracked | `f7dcb7df78167fc8` | purpose/status requires owner review |
| `Temp/state-backups/TASK-SERVER-START-20260831/LAST_HANDOFF.md` | ARCHIVE_CANDIDATE | untracked | `ae38f712778a8051` | report-like or dated artifact without canonical-state role |
| `Temp/task-switch-backup-20260831/ACTIVE_TASK.before.md` | HISTORICAL | untracked | `aa592e8ed3d002eb` | document marks itself historical/supporting |
| `work/active/TASK-DOCS-CANONICAL-20260901.md` | HISTORICAL | tracked | `80a7247d97949f84` | document marks itself historical/supporting |

## Duplicate documentation groups

- `EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md`, `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_STEP0.md`
- `EMAIL_DELIVERABILITY_ITERATION3_FINAL_REVIEW.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_FINAL_REVIEW.md`
- `EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md`, `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_LIVE_PLAN.md`
- `EMAIL_DELIVERABILITY_ITERATION3_STEP0.md`, `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_STEP0.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_STEP0.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_STEP0.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_STEP0.md`
- `EMAIL_DELIVERABILITY_ITERATION3_UI_GAP.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_UI_GAP.md`
- `EMAIL_PACING_ITERATION2_P0_CORRECTIVE_REPORT.md`, `P0_REVIEW_EXPORT/EMAIL_PACING_ITERATION2_P0_CORRECTIVE_REPORT.md`, `P0_REVIEW_VERIFY/EMAIL_PACING_ITERATION2_P0_CORRECTIVE_REPORT.md`
- `P0_REVIEW_EXPORT/00_README.md`, `P0_REVIEW_VERIFY/00_README.md`
- `P0_REVIEW_EXPORT/FILE_MANIFEST.md`, `P0_REVIEW_VERIFY/FILE_MANIFEST.md`
- `P0_REVIEW_EXPORT/P0_LIVE_STATE_SNAPSHOT.md`, `P0_REVIEW_VERIFY/P0_LIVE_STATE_SNAPSHOT.md`
- `REVIEW_EXPORT/00_README.md`, `REVIEW_EXPORT_VERIFY/00_README.md`
- `REVIEW_EXPORT/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md`, `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4.md`
- `REVIEW_EXPORT/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md`, `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_CAMPAIGN_UI_ITERATION4_REPORT.md`
- `REVIEW_EXPORT/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md`, `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md`, `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3.md`
- `REVIEW_EXPORT/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md`, `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md`, `REVIEW_PACKAGE_ITERATION4/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/EMAIL_DELIVERABILITY_ITERATION3_REPORT.md`
- `REVIEW_EXPORT/01_DOCUMENTATION/mail-integration.md`, `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/mail-integration.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/mail-integration.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/mail-integration.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/mail-integration.md`
- `REVIEW_EXPORT/01_DOCUMENTATION/messages-and-mail-audit.md`, `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/messages-and-mail-audit.md`
- `REVIEW_EXPORT/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md`, `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md`
- `REVIEW_EXPORT/01_DOCUMENTATION/PROJECT_STATUS.md`, `REVIEW_EXPORT_VERIFY/01_DOCUMENTATION/PROJECT_STATUS.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/PROJECT_STATUS.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/PROJECT_STATUS.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/PROJECT_STATUS.md`
- `REVIEW_EXPORT/FILE_MANIFEST.md`, `REVIEW_EXPORT_VERIFY/FILE_MANIFEST.md`
- `REVIEW_EXPORT/FINAL_REVIEW_SUMMARY.md`, `REVIEW_EXPORT_VERIFY/FINAL_REVIEW_SUMMARY.md`
- `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/messages-and-mail-audit.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/messages-and-mail-audit.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/messages-and-mail-audit.md`
- `REVIEW_PACKAGE_ITERATION4_FINAL_20260829_0939/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md`, `REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/01_DOCUMENTATION/PROJECT_DOCUMENTATION.md`
- `REVIEW_PACKAGE_ITERATION4_FINAL_V2/00_README.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/00_README.md`
- `REVIEW_PACKAGE_ITERATION4_FINAL_V2/FILE_MANIFEST.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/FILE_MANIFEST.md`
- `REVIEW_PACKAGE_ITERATION4_FINAL_V2/FINAL_REVIEW_SUMMARY.md`, `Temp/iteration4_review_verify/REVIEW_PACKAGE_ITERATION4_FINAL_V2/FINAL_REVIEW_SUMMARY.md`
