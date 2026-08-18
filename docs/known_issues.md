# Known expected failures

These are product, data, or environment gaps that are intentionally reported as `xfailed` by pytest. They are not counted as broken automation, but each one should eventually be removed when the application or fixture data supports the requirement.

| ID | Module | Area | Reason |
| --- | --- | --- | --- |
| KI-M1-TEMPLATE-001 | M1 | SME Excel template | Downloaded upload template does not expose a clear version marker. |
| KI-M1-TEMPLATE-002 | M1 | SME Excel template | Downloaded upload template may miss controlled columns or list validations. |
| KI-M1-TEMPLATE-003 | M1 | SME Excel template | Upload service may not reject a renamed legacy-version template or may reject it without a version-specific message. |
| KI-M1-SIRS-001 | M1 | RWG review | Current SIRS may expose fewer than the required 26 criteria across six sections. |
| KI-M1-FEEDBACK-001 | M1 | SME Sets | Current SME Sets screen does not expose feedback iteration metadata. |
| KI-M1-REJECTION-001 | M1 | SME/Admin rejection flow | Current environment may not expose a three-rejection item fixture, three-strike notification, or rejection history. |
| KI-M1-PIT-001 | M1 | PIT publication | PIT quorum verification needs a populated shared PIT queue and stable multi-login browser sessions. |
| KI-M1-REPOSITORY-001 | M1 | Item repository | Current Teacher navigation may not expose the Item Bank Repository. |
| KI-M1-QAR-001 | M1 | QAR results | Current QAR results summary does not expose rule-section details. |
| KI-M1-QAR-002 | M1 | QAR rules | Current QAR service does not flag the supplied bias/ambiguity fixture. |
| KI-M1-QAR-003 | M1 | QAR rules | Current QAR service does not enforce the 60% failure lock rule. |
| KI-M1-QAR-004 | M1 | QAR rules | Current QAR service does not enforce the 70% failure lock and exception-report rule. |
| KI-M1-TYPOLOGY-001 | M1 | Manual item typology | Live Item Typology dropdown no longer exposes "Multiple Choice Question" after Assertion and Reasoning, FA Activity, Free Response, and Source Based Question were added (confirmed via full-DOM inspection, not a scroll/render issue - the option is genuinely absent even after scrolling the select viewport to its end). Likely a product regression in the typology list source; needs dev-team investigation. |
| KI-M1-METADATA-001 | M1 | Metadata | Current dev manual-item form may miss mandatory metadata controls. |
| KI-M1-METADATA-002 | M1 | Metadata search | Current SME repository has no searchable published-item fixture. |
| KI-M1-METADATA-003 | M1 | Metadata | Current dev manual-item form does not expose a Stage control. |
| KI-M1-VALIDATION-001 | M1 | Manual item validation | Current manual-item editor does not emit an inline required error on blur. |
| KI-M1-VERSION-001 | M1 | Version history | Current SME Sets screen does not expose revision-history details or item-level IDs before opening a set. |
| KI-M1-QUEUE-001 | M1 | RWG/SRRWG/PIT review queue | A reviewer account may currently hold no assigned item set, so the smoke check cannot open one. Workflow-data state, not a product defect — advance a set to that stage to clear it. |
| KI-M3-ITM-001 | M3 | Item Testing | Current build exposes no Item Testing / psychometrics workspace (IRT 3PL calibration, ICC generation, DIF analysis), so TC-ITM-05..08 have no screen to exercise. |
| KI-M4-QP-001 | M4 | Question paper builder | Current QP Builder does not expose Hybrid creation mode. |
| KI-M4-QP-002 | M4 | Question paper builder | Auto-generation can fail when the current environment has no usable item pool/rules result. |
| KI-M4-SSO-001..002 | M4 | Teacher SSO | TIMS profile creation/unverified-user checks require TIMS/SSO fixture accounts. |
| KI-M4-ITEMBANK-001..003 | M4 | Item Bank | Metadata filtering/search/status visibility checks require a seeded item-bank performance fixture. |
| KI-M4-BUILDER-001..002 | M4 | Assessment Builder | Pagination and auto-save checks require stable builder UI/timing instrumentation. |
| KI-M4-DND-001..003 | M4 | Drag-and-Drop | DnD, marks tally, and competency map checks require cross-device execution and stable UI support. |
| KI-M4-QP-003 | M4 | Computer-Based Paper | Impossible auto-specification messaging requires reachable Auto Generator and fixture data. |
| KI-M4-RUBRIC-001..003 | M4 | Rubric Validation | Rubric engine validation requires compliant/non-compliant paper fixtures and stable violation output. |
| KI-M4-EXPORT-001..002 | M4 | QP Export | PDF/Word and answer-key validation require downloaded file rendering/content checks. |
| KI-M4-CREDIT-001..002 | M4 | Credit Tracking | Time-on-task and credit-score checks require audit/dashboard telemetry fixtures. |
| KI-M4-PERF-001 | M4 | Performance | 30-question PDF export SLA requires a seeded paper and download timing harness. |
| KI-M5-TEACHER-001 | M5 | Teacher contribution | Submitted teacher item may not be returned by the current Sets/QAR service. |
| KI-M5-SSO-001 | M5 | SSO Contribution | Unverified teacher checks require a safe negative TIMS/SSO account. |
| KI-M5-BLIND-001 | M5 | Teacher Review | Blind reviewer checks require a fresh teacher item routed to RWG. |
| KI-M5-LIFECYCLE-001 | M5 | IB2 Submission | Contributor-type persistence requires tracking a fresh teacher item through all lifecycle stages. |
| KI-M5-QAR-001..002 | M5 | QAR Teacher Items | Teacher QAR parity and exception reports require controlled teacher item fixtures. |
| KI-M5-FEEDBACK-001..003 | M5 | QAR Feedback | Feedback, revision, and disablement checks require teacher items in specific QAR states. |
| KI-M5-SIRS-001 | M5 | Teacher Review | Full SIRS check requires a fresh teacher item opened in RWG queue. |
| KI-M5-ROUTING-001 | M5 | Teacher Review | RWG-to-PIT routing validation requires safely advancing a fresh teacher item. |
| KI-M5-PIT-001..002 | M5 | PIT Teacher Items | PIT history and quorum checks require fresh one-time-vote teacher item sets. |
| KI-M5-IB2-001..002 | M5 | IB2 Publication | IB2 search/report checks require published teacher-item and Admin report fixtures. |
| KI-M5-RUBRIC-001..002 | M5 | Rubric Attachment | Rubric upload/download checks require teacher SEQ/LEQ item and reviewer fixtures. |
| KI-M5-CREDIT-001..003 | M5 | Contribution Tracking | Credit and milestone checks require PIT-approved/rejected teacher item fixtures. |
| KI-M5-PERF-001..005 | M5 | Performance | Teacher contribution SLAs and concurrent submissions require timing/load harnesses. |

| KI-M2-USER-001 | M2 | User Registration | Admin Create User UI may not be reachable/actionable in the current environment. |
| KI-M2-USER-002 | M2 | User Lifecycle | Safe disposable user fixture is required before deactivation tests can run without impacting shared users. |
| KI-M2-USER-003 | M2 | User Validation | Duplicate-email validation requires reachable Create User UI and a known existing user fixture. |
| KI-M2-USER-004 | M2 | User Validation | Duplicate-mobile validation requires reachable Create User UI and disposable test users. |
| KI-M2-RBAC-001 | M2 | RBAC | Sidebar/dashboard role markers may differ or be unavailable in the current UI. |
| KI-M2-RBAC-002 | M2 | RBAC | SME grade/subject access checks require the item-creation form and configured role restrictions. |
| KI-M2-MFA-001..006 | M2 | MFA/Onboarding | Email/SMS OTP and onboarding-link checks require external mailbox/SMS access or time-controlled fixtures. |
| KI-M2-SESSION-001..003 | M2 | Session | Idle timeout and warning tests are long-running timing checks best run in a dedicated session suite. |
| KI-M2-PORTAL-001..002 | M2 | Portal Settings | Theme/layout preview and publish controls may not be exposed in the current Admin UI. |
| KI-M2-DASHBOARD-001..002 | M2 | Dashboard | SME/PIT dashboard widget contracts depend on current role dashboards and fixture data. |
| KI-M2-AUDIT-001..002 | M2 | Audit Logs | Audit log filters and immutability checks require reachable Admin Audit Logs. |
| KI-M2-REPORTS-001..002 | M2 | Reports | Admin report generation/download checks require reachable Reports UI and report fixtures. |
| KI-M2-SUPPORT-001..002 | M2 | Support | Ticket creation and email acknowledgement require Support UI and mailbox access. |
| KI-M2-MASTERS-001..002 | M2 | Masters | Master-data create/delete checks require safe disposable master data and linked-item fixtures. |
| KI-M2-NOTIFY-001..002 | M2 | Notifications | Email/SMS notification checks require external notification channel access. |
| KI-M2-HEALTH-001..002 | M2 | System Health | Health dashboard/outage checks require reachable dashboard and controlled outage simulation. |
| KI-M2-PERF-001..003 | M2 | Performance | Rapid user creation, audit-log volume, and 100-user load tests require dedicated data/load environments. |
| KI-M2-QARCFG-001 | M2 | QAR Configuration | Admin QAR Configuration screen may not be reachable from the current Admin navigation. |
| KI-M2-QARCFG-002 | M2 | QAR Configuration | Global Settings controls (pass threshold, batch frequency, scheduled batch time) may not be readable/editable in the current build. |

When an item is fixed in the product or fixture data, remove the related `pytest.xfail(...)` from the test and let the assertion run normally.

## Open product question — Helpdesk 'Overdue' status vs the status tabs

`test_tc_wpad_helpdesk_02_verify_tab_filters` fails on every run, in the same
way, and it is the only genuine product finding the M2 suite currently
produces. It is left as a hard failure deliberately, pending a product answer.

**What happens:** the `In Progress` tab lists rows whose Status column reads
`['In Progress', 'Overdue']`. The test asserts a status tab shows only its own
status.

**Why it is ambiguous.** `HelpdeskPage` models Status and SLA as separate
things — `COLUMN_STATUS` (6) and `COLUMN_SLA_BREACH` (10, Yes/No) — and
`KNOWN_STATUSES` is `(Open, In Progress, Resolved, Closed)`, which does **not**
include `Overdue`. Yet `Overdue` is both a rendered Status value and a queue
tab. So either:

- **Product defect** — the `In Progress` filter is leaking tickets it should
  exclude; or
- **Test too strict** — `Overdue` is a derived status overlaying the workflow
  state, so an in-progress ticket past its SLA legitimately appears in both the
  `In Progress` and `Overdue` tabs.

**Do not weaken the assertion to make the suite green** until this is decided.
If the second reading is correct, the fix is to compare against the workflow
status underneath the SLA overlay (or to read `sla_breach` separately), not to
add `Overdue` to the list of accepted values — that would also stop the test
detecting a real leak of `Resolved` or `Closed` tickets into the tab. The same
ambiguity affects `helpdesk_04`, whose
`assert found["status"] in KNOWN_STATUSES` would fail for any overdue ticket.

## Test-data handling note

RWG, SRRWG, and PIT item-set actions are one-time workflow actions. An item set that was already acted on by RWG, SRRWG, or PIT should not be reused in a later test run for the same action path. Tests that exercise these reviewers must use a fresh eligible item set from the current queue or create/advance a new item set before taking the reviewer action.
