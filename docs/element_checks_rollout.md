# Element presence checks — phased rollout

Soft element checks record every element's verdict into the report instead of
failing the test at the first missing one. One run then answers "what is
actually rendered on this page?" rather than "which element broke first".

Mechanics live in [`utilities/element_checks.py`](../utilities/element_checks.py);
the report tables are built in `conftest.py` (`parse_element_checks`,
`build_element_checks_html`, `build_element_checks_text`).

## The rule that keeps this useful

**Soft-check structure. Hard-assert behaviour.**

| Assertion is about | Treatment | Example |
| --- | --- | --- |
| An element is on screen | soft | KPI card, filter dropdown, section heading, grid table |
| A page's structure | soft | grid has a Grade column, feed has entries |
| A workflow outcome | **hard** | user was created, deactivated login is blocked, item set reached QAR |
| A security contract | **hard** | teacher hitting `/admin` is denied, audit rows are immutable |
| A performance budget | **hard** | report generates within 5s |

Converting an outcome assertion to a soft check turns a real regression into a
report row nobody reads. A test whose *entire* body is soft checks can never
fail, so it stops gating anything — that is the correct trade only for tests
whose job is genuinely "inventory this page".

Every converted test should keep at least one hard gate. Reaching the page at
all (login + `wait_for_*_ready`) already counts as one.

## Usage

```python
checks = ElementChecks(page, record_property, page_name="Admin Dashboard")
checks.check("KPI card — Total Users", page.METRIC_CARD_TOTAL_USERS)
checks.check_condition("Grid has a Grade column", has_grade, detail=f"headers: {headers}")
value = checks.text_of(page.PAGE_HEADER)          # never raises
record_property("result_description", checks.publish())
```

The report renders the rows as a collapsible **Element Checks** block on each
test card, alongside Screenshot and Full Details / Traceback. It is collapsed by
default — a 60-row survey would otherwise bury the rest of the card — and opens
automatically when any row FAILED, so a gap is never one click away from
invisible. The summary line carries the counts either way.

Conventions that keep the report tables readable and greppable:

- `page_name` names the screen, optionally with a scope suffix —
  `"Admin Dashboard"`, `"Admin Dashboard — KPIs"`.
- Element names are prefixed by kind: `KPI card — `, `Filter — `, `Section — `,
  `Column — `, `Button — `.
- One `ElementChecks` per **test**, re-pointed as the test moves between
  screens (see below) — not one per page.
- Budget the time: every **absent** element costs its full timeout (default 5s).
  A 20-element survey on a broken page adds ~100s. Drop to `timeout=2` for
  large surveys of elements expected to render together.

### One collector per test — two collectors lose a table, one never does

`conftest` reads a test's properties with `dict(item.user_properties)`, so
repeated keys collapse to the **last** value written. That has two consequences
which look similar and are opposite:

- **Two different `ElementChecks` in one test → the first table is lost.** The
  second `publish()` overwrites it, silently. Never do this.
- **Re-publishing the *same* collector is safe.** `publish()` serialises its
  whole accumulated `results` list, so each call is a superset of the last and
  the final write wins with everything in it.

So a test that crosses several screens uses **one** collector, re-pointed at
each screen, and publishes as often as it likes:

```python
checks = ElementChecks(page, record_property, page_name="SME Manual Item")
survey_manual_form(checks, page)
checks.publish()                     # safe: table now holds phase 1
...
enter_screen(checks, "RWG — Opened Item Set")   # renames + screenshots
survey_opened_item_set(checks, review_page)
checks.publish()                     # table now holds phases 1 and 2
```

`enter_screen()` (in each module's `*_surveys.py`) sets `checks.page_name` and
files a screenshot, so every row keeps its own page name and each screen still
gets one shot — the thing a second collector was wanted for.

**Publish after every phase in a long chain.** A single publish at the end
loses the entire table if the chain breaks — exactly what happened to a
reviewer smoke check when the network dropped mid-test: it failed with no
element table at all, while the e2e chains that publish per phase would have
kept everything up to the break.

The same collapse applies to `result_description`; fold earlier summaries into
the final string rather than writing the key twice.

### Verify locators against the live DOM before writing checks against them

A locator that never matches produces exactly the same FAILED row as an element
the app genuinely failed to render, so an unverified locator reads as a product
gap. Resolving every new locator once against the live page (visible count and
in-DOM count) separates the two, and catches three things a census alone misses:

- **XPath that cannot compile.** `Bloom's Level *` in a single-quoted XPath
  raises `InvalidSelectorException` from the *reader*, taking the whole test
  down rather than recording one absent element. Quote label-driven locators
  through an `xpath_literal()` helper.
- **Locators that match their own ancestors.** An unscoped
  `contains(normalize-space(), …)` matched 13–20 elements up to `<body>`, so
  "present" meant "some container holds this text". Scope with `not(*)`.
- **Elements that are hidden by design.** The upload page's `<input type=file>`
  is in the DOM but never visible; check it for presence, not visibility.
- **Text XPath cannot see the way you can.** Two separate traps, both found by
  validation rather than by reading the page:
  - `text-transform: uppercase` — the preview's `GENERAL INSTRUCTIONS` heading
    is `General Instructions` in the DOM.
  - **visually-hidden sibling text** — each sidebar button carries a hidden
    tooltip span, so `innerText` is `"Home"` but `textContent`, which is what
    `normalize-space()` reads, is `"DashboardHome"`. Exact match never fires,
    and `contains('Item')` matches Repository, Create *and* Item. Match the
    label `<span>`, not the button.
- **Readers that outrun a debounce.** The My QP search empties the grid while
  its debounced query is in flight. Reading rows immediately returned zero and
  looked like a broken search; the control is fine. Wait out the debounce
  *before* polling for a settled result, or a working filter reports as dead.

### `check_interaction` is not free — never put one mid-workflow

Interaction checks *drive* the UI, so where they sit in a test matters. In the
M4 section-level suite, two mode-tab checks placed between "open the Auto
Generator" and "configure it" reset the generator form: the run then published
a **3-set** paper for a 4-set configuration and failed on a hard assertion that
had nothing to do with the checks.

The account was the obvious suspect and was innocent — running the *original*
test against both accounts passed, which is what isolated the real cause. Put
interaction checks before a workflow's setup begins, or after its assertions
finish; never between a step and the state it depends on.

### One role's census is not another role's screen

The RWG, Sr. RWG and PIT review queues look like the same page and are not.
Surveying all three against a census taken from RWG alone filed FAILED rows for
columns each screen is correct not to have:

| | Columns | Tabs | Distinctive |
| --- | --- | --- | --- |
| RWG | 11 | 6 | `Submitted By`, `Last Updated` |
| Sr. RWG | 10 | 6 | `Item Set Created Date`; no `Submitted By`/`Last Updated` |
| PIT | 13 | 5 | `PIT Votes`, `My Vote Status`, `Sr.RWG Review Date`; **no `Approved` tab** — PIT reviews to a quorum |

`QUEUE_COLUMNS` / `QUEUE_TAB_LABELS` now live on each role's page object, with
the base carrying the RWG shape. Census every role you intend to survey, or the
survey reports the difference between roles as a product gap.

### A survey helper reads attributes *outside* the guard

`ElementChecks` protects the *evaluation* of a check, not the argument passed
to it: `checks.check("Header", page.HEADER)` resolves `page.HEADER` before
`check` is ever entered. A page object missing that attribute raises
`AttributeError` and takes the whole test down — the same failure mode as
reading page state outside the guard, one level earlier.

`ManualItemPage` and `UploadItemFilePage` both extend `BasePage` directly, so
chrome locators added to one are absent from the other, and the M1 smoke check
would have crashed on the first survey. Worth a static check before a long run:
walk every (page object, survey) pair actually used and assert `hasattr` for
each attribute the survey touches. It costs seconds and caught this before a
three-hour pass.

### Only survey what the screen is supposed to show

A survey shared across modes must know which mode it is in. `Assessment
Configuration` and `Workflow Overview` are Manual Build cards — the Auto
Generator replaces them with `Choose Generation Level` / `Question Paper
Details`, so checking for all four in both modes filed FAILED rows for cards
the screen was right not to render. The same applies to genuinely optional
content: the preview's General Instructions section only exists when the author
supplied instructions, so it is recorded as content, not as a presence gap.

## Per-page screenshots

Constructing an `ElementChecks` also files a screenshot of that page into the
report's screenshot section, numbered in the order the pages were visited:

```
01 - Login
02 - Admin Dashboard — KPIs
03 - Audit Trail
PASS - 10/10 checks passed on Audit Trail
```

Nothing is needed in the test: a survey already names its page and is built at
the moment the test reaches that page. The shot is taken *before* the checks run,
so it shows the page as the test found it rather than as `check_interaction`
left it.

### The shutter waits for the page to paint

A survey is constructed the instant the test arrives, while the SPA may still be
on its global spinner. The checks that follow each wait up to their own timeout
for their element, so they pass — but the screenshot has no such patience, and
the first version of this filed `01 - Sign-in Form` as a picture of
"Loading sign in...". `wait_until_page_settled` now holds the shutter until:

| Signal | Why it is not photographable yet |
| --- | --- |
| `document.readyState` | still parsing |
| `[aria-busy="true"]`, `[role="progressbar"]` | the app says it is working |
| a short visible leaf reading `Loading ...` | this SPA's own global spinner. Leaf nodes under 60 chars only, so a content row starting with the word does not hold the shutter |
| a visible `<img>` mid-decode | photographs as a blank box |
| a CSS `background-image` not yet decoded | **invisible to `document.images`** — the sign-in hero lands ~3.4s after the DOM is ready, and the shot showed a flat gradient where the photograph belongs |
| DOM size + text length unchanged across two polls | a list still filling in |

Measured over five loads of the sign-in screen: four settled in 2.7–3.5s from
DOM-ready, most of it the hero artwork, and one needed longer than 8s for that
artwork alone. A page that is already settled clears in two polls (~0.3s), so
pages after the first in a session cost almost nothing — images and fonts are
cached by then.

Two deliberate escapes from that:

- **Fonts get 1.5s, not the full budget.** This environment blocks
  `Material Symbols Outlined` outright, so `document.fonts.status` sits on
  `loading` forever and the page renders ligature names (`mail_outline`) where
  the glyphs belong. Waiting the full cap on every page buys a picture that will
  never improve. The icon-font question belongs to `is_font_loaded`, which
  records a proper report row for it.
- **`capture(..., settle=False)`** for a state that is *meant* to be transient —
  a toast, or a spinner you are documenting on purpose — where waiting would
  photograph the page after the thing had gone.

The cap is 15s, tunable with `CBSE_EVIDENCE_SETTLE_TIMEOUT`. When it expires the
shot is taken anyway: a page still loading after 15s is itself the evidence. It
is deliberately well clear of the ~3s typical settle — at 8s the slow tail above
produced exactly the half-painted screenshot this wait exists to prevent.

### It applies to every screenshot, not just the per-page series

The wait lives in `ScreenshotUtils.capture` (`settle=True` by default), so it
covers all of it: the per-page series, the end-of-test PASS shot, the M1/M5 e2e
tests that file evidence through their own helpers, and the page-object helpers
that shoot an OCR/reviewer/QAR success state. `page_settle.py` is a module of its
own because `screenshot_utils` and `page_evidence` both need it.

One call site opts out: the **FAIL** screenshot in `conftest`. When a test fails
on a page that is stuck loading, the stuck page is the finding, and waiting the
full budget for it on every failure buys nothing.

The series arrives in all three outputs — collapsed `<details>` blocks on the
Extent card, a gallery on the pytest-html card, and one line per shot in the
Excel `Screenshots` column. A single end-of-test screenshot only shows where a
test stopped; the series shows the route it took, which is what a failure three
pages deep needs.

For checkpoints that are not a survey — a login screen, a toast, a popup — ask
for the fixture and capture directly:

```python
def test_something(self, record_property, page_evidence):
    page_evidence.capture("Login")            # 01 - Login
```

Both paths append to one list, so numbering stays continuous no matter which
records the shot. Pass `capture_evidence=False` when a second `ElementChecks`
surveys a page an earlier one already photographed. A capture never fails a
test: no driver, a dead session, or an unwritable path costs the screenshot and
nothing else.

Cost: one full-page PNG per page, embedded base64 in the self-contained reports.
Budget roughly 200-300KB per page surveyed.

## Visual checks (branding, colour, theme)

Presence answers "is it on the page". Branding questions — the right logo, the
brand palette, the background artwork, the theme — need what the element *looks
like*, so `LoginPage` grows a set of readers that return an empty/False value
instead of raising:

| Reader | Answers |
| --- | --- |
| `get_computed_style` / `get_settled_computed_style` | painted colours, radius, font — settled variant waits out CSS transitions |
| `get_theme_palette` / `get_active_theme` | the `--primary`-style variables the page draws from, and the live `data-theme` |
| `is_image_rendered` / `get_image_source` | whether a logo decoded pixels, not just whether the `<img>` exists |
| `get_background_image_url` / `is_image_url_loaded` | referenced artwork (hero background, favicon), where a 404 leaves no DOM trace |
| `is_font_loaded` / `get_loaded_font_families` | brand and icon fonts — waits on `document.fonts.ready`, since a bare `check()` races the lazy download |
| `open_theme_menu` / `select_theme` | the theme picker, returning the theme the app *settled on* rather than the one asked for |

Two traps these exist to avoid: a broken image still passes a presence check
(it keeps its box and shows alt text), and an icon font that failed to load
renders its ligature names as literal text (`mail_outline` beside the email
field) — neither is visible to a locator.

Colours are compared through the test's `to_rgb()`, because the palette is
declared as hex in the CSS variables but reported as `rgb()` by
`getComputedStyle`; a string comparison calls identical colours a mismatch.

## Progress

| | Tests | Files |
| --- | --- | --- |
| Converted | 4 | 1 |
| Added — login-screen visual survey (M5) | 2 | 1 |
| Converted — M5 teacher contribution | 13 | 3 |
| Converted — M4 QP creation | 3 | 3 |
| Converted — M1 item bank | 49 | 15 |
| M2 pending — Phase 2 | 29 | 5 |
| M2 pending — Phase 3 | 31 | 6 |
| M2 out of scope | 13 | 3 |
| **M2 total** | **77** | **15** |
| Remaining — M3 | 1 | — |

## Phases

Each phase is independently shippable and leaves the suite runnable.

### Phase 0 — infrastructure + pilot ✅ done

- `utilities/element_checks.py`, conftest renderers, Extent/pytest-html/Excel wiring
- Pilot: `test_tc_wpad_dash_02` (18 checks, verified green on the live environment)

### Phase 1 — finish the pilot page ✅ done

`tests/M2_Web_Portal_Admin/test_admin_dashboard.py` — remaining 3 tests
(`dash_01` KPI cards + values, `dash_03` activity feed, `dash_04` published
grid). Proves the pattern across presence checks, content checks and safe text
reads on one page object.

### Phase 2 — read-only M2 survey suites (29 tests, 5 files)

Highest value, lowest risk: these already assert "does this page render", which
is exactly what soft checks are for. No state mutation, so no cleanup concerns.

| File | Tests | Notes |
| --- | --- | --- |
| `test_item_bank.py` | 6 | Item Bank Overview columns, filters, pagination |
| `test_role_management.py` | 5 | role grid, search, pagination controls |
| `test_audit_trail.py` | 4 | keep the immutability assertions **hard** — security contract |
| `test_notifications_health_performance.py` | 7 | keep the 3s/5s timing assertions **hard** |
| `test_qar_configuration.py` | 7 | tab rendering soft; threshold/config values hard |

Exit criteria: full-file headless run per file, element tables populated, no
change in each file's pass/fail count versus the pre-change baseline.

### Phase 3 — M2 workflow suites (31 tests, 6 files)

Mixed: survey the page softly, keep the workflow outcome hard. Convert the
setup/navigation assertions only.

| File | Tests | Keep hard |
| --- | --- | --- |
| `test_portal_admin_features.py` | 12 | theme publish, master-data delete-blocked, report download |
| `test_user_management_rbac.py` | 7 | create/deactivate outcomes, RBAC denials |
| `test_helpdesk_management.py` | 5 | tab filter correctness (a real bug lives here) |
| `test_assignment_queue_basics.py` | 5 | assignment results |
| `test_support_ticketing.py` | 1 | ticket created and attributed |
| `test_assignment_rules.py` | 1 | unassign/reassign outcome; `serial` |

### Phase 4 — run-level summary

Report plumbing, not test edits. Add a "Missing Elements" section to the Extent
report aggregating every FAILED element row across the run, grouped by page, so
the data is actionable without opening each test card. Optionally fail the run
when an element that has always been present disappears — that restores the
regression gate the soft checks give up.

### Phase 5 — other modules

`M1_Item_Bank_Mgmt`, `M4_QP_Creation`, `M5_Teacher_Contribution`. Defer until
Phase 4 exists: these suites are long and stateful, and without the run-level
summary the extra rows are noise rather than signal. Skip the `e2e_` tests —
they are workflow assertions end to end.

Landed early: `TestTeacherLoginPageBranding` in
`tests/M5_Teacher_Contribution/test_teacher_login.py` (65 checks across a
branding survey and a theme-switcher test). It is neither long nor stateful —
it signs nobody in, so it does not contend for the shared teacher session — and
the login screen is the one page every module's users see first.

#### M5 — done

| File | Tests | Checks | Survey scope | Kept hard |
| --- | --- | --- | --- | --- |
| `test_login_negative_cases.py` | 8 | 98 | sign-in form furniture | every password-policy rejection, the bad-password error state, the dashboard landing |
| `test_teacher_manual_item_creation.py` | 4 | 198 | teacher dashboard; manual authoring form | greeting renders, stat counters numeric + no bucket exceeds the total, Continue locked until an item is added, grade/subject RBAC |
| `test_upload_history_excel_download.py` | 1 | 38 | upload step + Previously Uploaded Files | an account with both PASSED and FAILED rows exists, both files download, open as workbooks and are distinct |

Headless baseline on the QA environment: **18 passed, 399 element checks, 0 failed**
(includes the 65-check login branding pair and the 2 smoke checks, both unchanged).
17 of those checks are interactions — 11 dashboard tabs and stat cards, 3
prerequisite tabs, 2 password-visibility toggles, 1 Clear Form.

A clean sheet is the point of a baseline, not a sign the survey is toothless:
every locator was resolved against the live DOM first, so a FAILED row from here
means the app stopped rendering something it rendered on 2026-08-17.

`test_teacher_login.py`'s `test_teacher_valid_login`, the `test_e2e_*` files and
`test_smoke_m5_teacher_contribution.py` were deliberately left alone — the first
is the smoke gate's login check, and the rest are end-to-end workflow
assertions.

#### M1 — done

SME-driven, across the manual authoring form, the bulk upload step and the My
Item Set listing. Surveys live in `tests/M1_Item_Bank_Mgmt/m1_surveys.py`.

| File | Tests | Kept hard |
| --- | --- | --- |
| `test_sme_manual_item_creation.py` | 13 | typology inventory (behind its xfail guard), per-typology create + QAR outcome, required-field blocking |
| `test_sme_manual_item_validation.py` | 4 | Continue locked until complete, real item ID in draft review, subject RBAC, empty-content validation |
| `test_sme_bulk_upload_rbac.py` | 1 | grade/subject scope, *and* that rows rendered at all |
| `test_negative_non_xlsx_upload_rejected.py` | 1 | every rejection message, Continue stays disabled, valid file still accepted |
| `test_qar_duplicate_detection.py` | 1 | duplicate flagged, QAR counts reconcile — **pre-existing failure, see below** |
| `test_upload_file_size_limit.py` | 1 | 10 MB limit message, no upload ID issued, API 413 |

Headless baseline: **20 of 21 passed, 585 element checks, 0 failed**.

`test_qar_duplicate_detection` fails, and **not because of this conversion** —
three runs settle it:

| Code | Outcome |
| --- | --- |
| pre-change, straight from git | failed — `TimeoutException` |
| converted, run 1 | failed — `assert 0 >= 5`, baseline set held 1 item not 5 |
| converted, run 2 | failed — `TimeoutException` |

Both timeouts land on the same call, `click_submit_for_qar_and_wait_for_results()`
at `test_qar_duplicate_detection.py:105` — the wait for QAR analysis to finish.
The test is stuck on the QAR service, which is also why the symptom moves
between runs. Its element table is 39/39 either way, and the survey runs before
any workbook is uploaded, so it cannot be implicated.

**The two `pytest.xfail` guards for KI-M1-TYPOLOGY-001 were left exactly as they
were**, and each survey publishes *before* the guard can fire — an xfail must
not cost the record of what the page rendered when the known issue hit.

Worth noting for whoever owns that known issue: the live dropdown now offers
**all 12** controlled typologies including Multiple Choice Question, so the
guard's condition no longer holds on this environment and it simply will not
fire. The guard stays regardless; it is not this rollout's call to retire it.

**M1 is now fully covered — 49 of 49 tests.** The second pass added the five
`test_e2e_*.py` chains, `test_manual_item_rich_content_to_pit_publication.py`,
both `test_smoke_m1_*.py` files and `test_sme_cross_rbac_api.py`.

Two corrections to earlier reasoning, both worth carrying forward:

- `test_sme_cross_rbac_api.py` is **not** DOM-free. It signs in through a real
  browser to harvest cookies and a bearer token before switching to `requests`,
  so it has an authenticated landing page worth surveying. "API test" is not
  the same as "no DOM".
- The smoke files now carry surveys too, by explicit decision. **Every existing
  assertion stayed exactly as hard as it was** — the element table is extra
  evidence on the card, not a replacement gate — so the rule below still holds
  in substance: nothing about the smoke gate was softened.

In the long e2e chains the collector is re-published after *each* phase.
`publish()` writes the whole accumulated list, so re-publishing is safe and
means a failure late in a SME → QAR → RWG → Sr. RWG → PIT chain still leaves
every row gathered up to that point on the report card. A single publish at
the end loses the entire table when the chain breaks — which is exactly what
happened to a reviewer smoke check when the network dropped mid-test.

#### M4 — done

All three QP workflow suites, surveyed across the four screens each one walks.
The smoke pair is untouched apart from account resolution.

| File | Tests | Checks | Kept hard |
| --- | --- | --- | --- |
| `test_qp_autogenerate_item_level_preview.py` | 1 | 112 | ≤10s generation budget, published metadata matches the configuration, 2 sections, 4 sets |
| `test_qp_autogenerate_section_preview.py` | 1 | 112 | as above |
| `test_qp_manual_build_preview.py` | 1 | 84 | marks fully allocated, published metadata, 1 section |

Headless baseline: **5 passed, 308 element checks, 0 failed** (7m42s).

The shared surveys live in `tests/M4_QP_Creation/qp_surveys.py` — all three
suites walk the same screens, and `enter_screen()` re-points one collector at
the next screen and photographs it, so each test still publishes exactly once
while every row keeps its own page name.

`pages/teacher/question_paper_builder_page.py` had **two** named locators for
the entire builder; the rest of its controls are found dynamically in JS. It
now carries ~50 plus survey readers.

One pre-existing weak assertion, left in place but worth knowing about:
`get_header_metadata_text()` returns every element whose text contains "Marks"
or "Questions", which on a question paper is nearly the whole document — so the
suites' `assert "marks" in header_text` passes on any paper page. The new
`get_header_chip_texts()` reads the three real toolbar chips
(`30 min`, `10 Marks`, `8 Questions`) and the surveys use that instead.

The teacher dashboard is the case the inventory step exists for:
`pages/teacher/dashboard_page.py` held **one** locator (`DASHBOARD_TEXT`) while
the screen renders seven stat cards, six charts, seven grid tabs, a ten-column
grid, pagination, eight nav destinations and the accessibility toolbar. A survey
written against the old page object would have reported "1/1 present".

Two behaviours the census settled that guesswork would have got wrong:

- The grid **tabs filter in place**, but the **stat cards navigate** to
  `/item-sets?tab=<status>`. An interaction check that verified a stat card
  against the dashboard would have passed against the *destination* page, and
  driving them before the content assertions moved the test off the dashboard
  entirely — which the hard gate caught.
- The grid **re-columns itself per tab**: item-set tabs show `ITEM_SET_COLUMNS`,
  `Draft-Items` shows `DRAFT_ITEM_COLUMNS`.

## Explicitly out of scope

- `test_mfa_session_contracts.py` (9) and `test_e2e_user_lifecycle.py` (1) —
  already `xfail`/manual against this environment; converting them adds rows
  without adding information.
- `test_smoke_m2_web_portal_admin.py` (3) — the smoke gate must fail loudly and
  fast. Soft checks defeat its purpose.
