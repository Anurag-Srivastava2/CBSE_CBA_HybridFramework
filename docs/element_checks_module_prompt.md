# Reusable prompt — roll element checks out to another module

Paste the block below into a fresh session, replacing `M4_QP_Creation` with the
target module folder. Everything it depends on already exists in the repo; no
infrastructure needs rebuilding.

---

## The prompt

> Apply the element-check pattern already implemented in
> `tests/M2_Web_Portal_Admin/` to **`tests/M4_QP_Creation/`**.
>
> **Read these first** so you match the existing pattern rather than inventing one:
> - `utilities/element_checks.py` — the `ElementChecks` collector
> - `conftest.py` — `parse_element_checks` / `build_element_checks_html` /
>   `build_element_checks_text`, and where they are wired into the passed and
>   failed branches of `pytest_runtest_makereport`
> - `tests/M2_Web_Portal_Admin/test_admin_dashboard.py` — the fullest example
>   (a 55-check page survey plus interaction checks)
> - `tests/M2_Web_Portal_Admin/test_item_bank.py` — the `survey()` helper pattern
>   shared across a test class
>
> **The rule that governs every conversion — soft-check structure, hard-assert behaviour:**
>
> | The assertion is about | Treatment |
> | --- | --- |
> | An element is on screen | soft — `checks.check(...)` |
> | Page structure (columns, tabs, KPI cards, sections) | soft — `checks.check_condition(...)` |
> | A control responds when driven | soft — `checks.check_interaction(...)` |
> | A workflow outcome (created, submitted, published) | **hard `assert`** |
> | A security or RBAC contract | **hard `assert`** |
> | A performance budget | **hard `assert`** |
> | Data integrity (counts reconcile, export contents) | **hard `assert`** |
>
> A test whose entire body is soft checks can never fail. That is correct only
> for tests whose job is genuinely "inventory this page". Every other converted
> test keeps at least one hard gate.
>
> **Work one file at a time, in this order:**
>
> 1. **Inventory the real page before writing any check.** Write a throwaway
>    script (see `docs/element_checks_rollout.md`) that logs in headless, opens
>    the page, and prints a census: visible `<img>` with alt/src, `<svg>` classes,
>    landmarks (`header`/`nav`/`main`/`table`/`canvas`), every visible `<button>`
>    and `<a>` label, and every `h1`-`h4`. On the M2 dashboard this found **37
>    elements the page object had no locators for** — the logo, 40 icons, 13 nav
>    items, and 5 of 9 sections. Skipping this step produces a survey that reports
>    "18/18 present" when it is really 18 of 55.
>
> 2. **Add the missing locators to the page object**, not to the test. Group them
>    with comments (branding/chrome, sections, tabs, nav, icons). Prefer stable
>    component classes (`svg.lucide-file-text`) over text where the text is
>    truncated by CSS. If a locator could match more than one element on the page,
>    scope it from its own heading — a bare `//table` matched the wrong grid on the
>    M2 dashboard, which has two.
>
> 3. **Add a `survey(self, page, record_property, scope)` helper** to the test
>    class that soft-checks the page furniture, and call it from every test in
>    that class with a distinct `scope` string. Exclude controls that only exist
>    after an interaction (selection summaries, toasts, modals) so their absence
>    on arrival is not recorded as a gap.
>
> 4. **Convert the assertions** per the table above.
>
> 5. **Add interaction checks** for every search box, filter dropdown, tab, radio,
>    and toggle: `checks.check_interaction(name, action, verify)`. This is the
>    check that catches a rendered-but-dead control, which every presence check
>    passes.
>
> 6. **Verify** with `pytest tests/M4_QP_Creation --collect-only -q`, then run it
>    headless and report the element tables.
>
> **Four mistakes to avoid — all of them were made and fixed during the M2 rollout:**
>
> - **Never read page state outside the guard.** `missing = page.missing_columns()`
>   on its own line raises straight through and kills the test — the exact failure
>   mode soft checks exist to prevent. Use `checks.safe_call(page.missing_columns)`,
>   and pass predicates to `check_condition` as callables
>   (`lambda: page.is_on_page()`, not `page.is_on_page()`) so they are evaluated
>   inside the try.
> - **Never delete an existing `pytest.xfail(...)` guard.** Those encode known
>   product gaps (`KI-M2-*` in `docs/known_issues.md`). Removing one lets the test
>   run on to an assertion that never previously executed and fail for reasons the
>   page state cannot support. Record the markers softly *in addition to* the
>   guard, and keep the guard ahead of any hard assertion that depends on the page
>   having rendered.
> - **Budget the timeouts.** Every *absent* element costs its full timeout
>   (`ElementChecks.DEFAULT_TIMEOUT` is 5s). A 20-element survey on a broken page
>   adds ~100s. Pass `timeout=2` for large groups expected to render together.
> - **Do not soften the smoke suite.** `test_smoke_*.py` must fail loudly and fast;
>   soft checks defeat its purpose.
>
> **Naming conventions**, so the report tables stay readable and greppable:
> `page_name` is the screen with an optional scope suffix (`"QP Builder — Filters"`);
> element names carry a kind prefix (`"Filter — Grade"`, `"Tab — My QP"`,
> `"Column — Status"`, `"KPI card — Total"`, `"Nav — Home"`).
>
> Report at the end: tests converted, checks added per file, which assertions you
> kept hard and why, and the headless run's pass/fail plus element tables.

---

## Module facts to fill in

| Module | Tests | Driving account | Notes |
| --- | --- | --- | --- |
| M4 - QP Creation | 5 | `teacher2` | QP Builder, Assessment Configuration, My QP listing |
| M5 - Teacher Contribution | 14 | primary teacher | Long stateful flows; skip the `test_e2e_*` files |
| M1 - Item Bank Mgmt | 25 | SME | `get_sme2_username()` is already worker-aware |
| M3 - Item Testing | 1 | admin | Currently `xfail` as KI-M3-ITM-001 |

## If you also want that module to run in parallel

The portal keeps **one active session per account**, so N workers need N distinct
accounts for the role that module drives. `ReadConfig.get_admin_username()` and
`get_sme2_username()` already split per worker off `PYTEST_XDIST_WORKER`.

`get_teacher_username()` now does the same for teacher-driven modules — ✅ added
during the M5 rollout, along with `get_teacher_usernames()` (pool, primary
first) and `get_teacher_password()`. M5 call sites are repointed.

M4 is repointed too, but to its own resolver: `get_qp_teacher_username()`,
drawing from a pool that **excludes the primary teacher** (teacher2-5 here).
Every QP suite publishes into "My QP" and its preview step opens the newest
paper in that list, so it must not share an account with a concurrently running
suite. The M4 files previously hardcoded their accounts, which had gone wrong
in both directions: `test_qp_autogenerate_section_preview.py` drove the
*primary* teacher — the account M5 uses — while the item-level and manual-build
suites both drove teacher2 and so collided with each other under `-n 2`.

Parallelism is capped by the number of configured accounts. This environment
configures **five** teachers in `CBSE_TEACHER_USERNAMES`, so `-n 5` is the
maximum; `-n 6` hands worker 5 the same account as worker 0 and the two sign
each other out. Always pass `--dist loadgroup` so `serial`-marked tests stay on
one worker.

One trap when repointing call sites: **never call a worker-aware resolver at
collection time.** `test_login_negative_cases.py` builds its usernames inside a
`@pytest.mark.parametrize` list, whose values become test IDs — and pytest-xdist
requires every worker to collect *identical* IDs, so a per-worker username there
fails the run outright rather than distributing it. Those rows stay on
`get_username()` (they never establish a session, so they never contend);
only the runtime call sites move to `get_teacher_username()`.
