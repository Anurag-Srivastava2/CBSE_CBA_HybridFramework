# Jenkins pipelines

Three pipeline definitions live in the repo root. They share their steps
through [ci/jenkins/cbse.groovy](../ci/jenkins/cbse.groovy), which each one
`load`s after `checkout scm`.

| File | Job | Runs | Typical time |
| --- | --- | --- | --- |
| [Jenkinsfile](../Jenkinsfile) | `cbse-smoke` | 15 critical-path checks across M1–M5 | ~15 min |
| [Jenkinsfile.module](../Jenkinsfile.module) | `cbse-M1` … `cbse-M5` | one module | minutes to ~2 h |
| [Jenkinsfile.full](../Jenkinsfile.full) | `cbse-full` | the five module folders (148 tests), in parallel lanes | bounded by the M1+M5 lane |
| [Jenkinsfile.full](../Jenkinsfile.full) | `cbse-daily` | the same, every day at 10:00 IST, mailed to the team | as above |

The smoke gate is the post-deployment gate and is documented separately in
[jenkins_setup.md](jenkins_setup.md) — agent prerequisites, the `cbse-smoke-env`
credential and the deployment trigger described there apply to all three jobs.

## Creating the jobs

All three are *Pipeline* jobs configured as **Pipeline script from SCM**; the
only difference is **Script Path**:

| Job | Script Path | Notes |
| --- | --- | --- |
| `cbse-smoke` | `Jenkinsfile` | |
| `cbse-M1` … `cbse-M5` | `Jenkinsfile.module` | five jobs, same file, `MODULE` set per job |
| `cbse-full` | `Jenkinsfile.full` | by hand |
| `cbse-daily` | `Jenkinsfile.full` | scheduled; see [Daily regression](#daily-regression) |

Build each module job once so Jenkins records its parameters, then set the
per-job default by editing `MODULE` in the job configuration. (A single job
with `MODULE` chosen at build time also works, but five jobs give five
independent build histories and trend graphs, which is usually what you want.)

Plugins: **AnsiColor**, **HTML Publisher**, **JUnit** (all already required by
the smoke gate) plus **Lockable Resources** for the account lock below and
**Email Extension** for the daily mail.

## Daily regression

`cbse-daily` is `Jenkinsfile.full` under a second job name. The file switches
two things on for that name only:

- **Schedule**: `cron('TZ=Asia/Kolkata
0 10 * * *')`, 10:00 IST every day.
  Jenkins registers a declarative trigger when a build runs, so **build the
  job once by hand** after creating it; the schedule applies from the next day.
- **Team mail** (`SEND_REPORT` defaults to on): when the build finishes,
  whatever the result, the team gets one module-level summary.

Setup, once:

1. New Item → Pipeline → name it exactly `cbse-daily` → Pipeline script from
   SCM, Script Path `Jenkinsfile.full`.
2. Manage Jenkins → System → **Extended E-mail Notification**: SMTP server,
   and the team list in **Default Recipients**. `NOTIFY_EMAILS` overrides it
   per build, but a scheduled build uses the Jenkinsfile defaults, so the team
   list belongs in Jenkins config rather than in the parameter.
3. Build once by hand.

Scheduled builds always run with the **Jenkinsfile's** parameter defaults.
Editing a default in the job UI does not stick, because each declarative build
rewrites the job's parameters. To point the daily run at another environment,
change `CBSE_BASE_URL`'s default in the file and swap the `cbse-smoke-env`
credential to that environment's accounts.

### The summary

[tools/build_daily_summary.py](../tools/build_daily_summary.py) merges every
lane's `junit.xml` and regroups by **module**, because the lanes are drawn
along account lines (M1 shares with M5, M2 is split in two) and are the wrong
cut for a status report. It writes `reports_ci/daily_summary.html` (the mail
body, also published as **CBSE Summary** on the build) and lists:

- pass/fail/skip/xfail counts and pass rate per module (a module whose lane
  crashed shows as "no results" rather than disappearing);
- **Failed tests**: candidate product defects;
- **Environment issues**: failures with a transport-level signature, using the
  same `is_infrastructure_failure()` classification as the run report. Config
  errors such as a missing env var still land under failed tests.

Run it locally against any reports directory:
`python tools/build_daily_summary.py --reports-dir reports_ci`.

Jenkins' default Content Security Policy strips inline styles from published
HTML, so the **CBSE Summary** page renders plain in the browser; the mail is
unaffected.

**10:00 is working hours.** The account lock keeps other Jenkins jobs off the
portal accounts, but not people or local runs. A local pytest run using the
same `.env` accounts during the daily build will sign its sessions out, and
those failures look like product defects in the mail.

## Where the parallelism comes from

Two layers, and the difference matters:

**Inside a pytest process**, `pytest-xdist` with `--dist loadgroup` spreads
tests across workers while keeping every `xdist_group` on a single worker. The
suite uses those groups to encode account ownership — per-account groups plus
one global `serial` group — so this scheduler is what stops two workers signing
each other out of the same portal account. `--dist loadgroup` is not a tuning
choice; any other scheduler breaks the suite.

**Across pytest processes**, `Jenkinsfile.full` runs three lanes at once. The
lanes are drawn along *account* boundaries rather than directory boundaries,
because several modules share accounts:

| Lane | Paths | Accounts | Tests |
| --- | --- | --- | --- |
| M2 | `tests/M2_Web_Portal_Admin` minus `serial` | admin (+ admin2 if configured), sme3, teacher7 | 56 |
| M3 + M4 | `tests/M3_Item_Testing`, `tests/M4_QP_Creation` | teacher3 | 8 |
| M1 + M5 | `tests/M1_Item_Bank_Mgmt`, `tests/M5_Teacher_Contribution` | sme1, teacher1 (+ teacher2 for the triple-revision e2e), RWG/SR-RWG/PIT | 75 |
| *(tail)* M2 serial | `tests/M2_Web_Portal_Admin` `serial` only | admin + RWG | 9 |

The SME and teacher columns assume the default workers (1/1/1 since 2026-10-05; it was 2/1/1) and the QA pools
`CBSE_SME_USERNAMES=sme1..sme4@dev.com` and
`CBSE_TEACHER_USERNAMES=teacher1,teacher2,teacher7,teacher3@dev.com` (2026-10-01).
Each xdist worker gwN takes entry N of a pool, and the M2 and M3+M4 lanes add
`CBSE_ACCOUNT_SLOT_OFFSET=WORKERS` (at least 2: the triple-revision e2e always drives teacher2), so they start past the accounts M1+M5 holds
(M4 draws on the teacher pool minus its first entry). Pools wrap, so raising a
worker count past the pool length puts two lanes back on one account.

Counts as of 2026-09-30. **Not in the daily/full run, by decision on
2026-09-30:** `tests/_unit` (122 tests) and the two top-level files
`tests/test_qar_retry_flow.py` and `tests/test_manual_typology_coverage.py`
(15). The `cbse-M1` module job still runs them.

Three consequences worth knowing before you edit the lanes:

- **M1 and M5 must share one process.** Both drive the
  RWG/SR-RWG/PIT reviewer pool, and they share `tmp_uploads/`. In one process
  xdist's global `serial` group covers both at once; split into separate
  processes, each keeps its own serial worker and they double-book the
  reviewers. Splitting M1 from M5 does not make the build faster, it makes it
  flaky.
- **`tests/_unit` is misnamed.** 14 of its 22 files drive a real browser
  against SME2 and the reviewer accounts. If it is ever put back into the
  full run, it must go in the M1+M5 process, not a lane of its own.
- **M2's `serial` tests run last, alone.** One of them deactivates every RWG
  account to prove that assignments get reassigned, restoring them in a
  `finally`. Running that while M1 and M5 hold reviewer sessions fails them for
  a reason that is not a product defect.

The M1+M5 lane is the critical path; everything else finishes underneath it. So
`WORKERS` is the parameter that decides how long a full build takes, and real
extra parallelism needs **more accounts**, not more lanes — see
[jenkins_setup.md](jenkins_setup.md) section 6.

### Coverage

The full/daily lanes cover the five module folders exactly: no test in two
lanes, none in none. The module jobs cover more: the M1 job also owns
`tests/_unit` and the two pure-Python files, which the full run leaves out.
The table below predates the 2026-09-30 counts above:

| Module job | regression | smoke | nightly |
| --- | --- | --- | --- |
| M1 (incl. `tests/_unit`, `tests/test_*.py`) | 155 | 7 | 25 |
| M2 | 77 | 3 | 0 |
| M3 | 1 | 0 | 0 |
| M4 | 5 | 2 | 0 |
| M5 | 19 | 3 | 0 |

`tests/_tmp_report_check/` is the one directory no job runs: it holds synthetic
pass/skip/retry fixtures for checking the report renderer, including a
deliberate first-attempt failure.

Note the zeroes. All 25 nightly tests are in M1, and M3 has no smoke check, so
those combinations select nothing. pytest exits 5 on an empty selection and the
pipeline fails the build rather than reporting green for a run that did
nothing.

## Keeping builds off each other

Overlapping builds are the single largest source of false failures here,
because the portal allows one active session per account and the accounts are
shared across jobs. Two guards:

- `disableConcurrentBuilds()` stops a job overlapping itself.
- `lock(resource: params.ACCOUNT_LOCK)` — default `cbse-cba-accounts` — stops
  *different* jobs overlapping. `cbse-full` holds it across both the parallel
  lanes and the serial tail, so a module build queues rather than interleaving.

The lock is taken around the test phase only, so checkout and `pip install` do
not sit in the queue. Testing a second environment concurrently means giving it
its own accounts *and* its own `ACCOUNT_LOCK` value; sharing accounts across
environments and relying on the lock only serialises the builds.

## Parameters

Shared by the module and full pipelines:

| Parameter | Default | Notes |
| --- | --- | --- |
| `CBSE_BASE_URL` | QA | Environment under test. |
| `WORKERS` | `2` in `cbse-full`, `4` in the module job | xdist workers. Each drives a headless Chrome (~200 MB). In `cbse-full` this applies to the M1+M5 lane, the critical path. Lowered from 4 on 2026-09-30: the portal rate-limits sign-ins per machine, and 7 parallel browsers cost 16 tests to lockouts in build #2. |
| `RERUNS` | `0` | See below. |
| `ACCOUNT_LOCK` | `cbse-cba-accounts` | Lockable resource name. |

`Jenkinsfile.module` adds `MODULE` (M1–M5) and `SUITE`
(`regression` / `smoke` / `nightly` / `performance`). `Jenkinsfile.full` adds
`LIGHT_WORKERS` (M3+M4 lane), `M2_WORKERS` (M2 lane; default `1`, because each
worker needs its own admin account and only one is usually configured), peak
browsers being `WORKERS + LIGHT_WORKERS + M2_WORKERS` (2 + 1 + 1 = 4 by default), plus `INCLUDE_NIGHTLY`,
`INCLUDE_PERFORMANCE`, `SEND_REPORT` and `NOTIFY_EMAILS`.

Every lane's `-m` expression excludes `deferred`, as `pytest.ini` does. It has
to be restated because a command-line `-m` replaces the one in `addopts`.

### On `RERUNS`

It defaults to `0`, which does **not** mean "no retries". The suite already
carries `@pytest.mark.flaky(reruns=1, reruns_delay=5)` on the classes with a
known transient — chiefly the portal's intermittent sign-in stall — and those
markers keep working. `RERUNS` adds a *blanket* retry on top, which hides real
regressions and doubles the cost of a genuine failure, so raise it to `1` only
for an environment you already know is noisy.

The cheaper defences against false failures are already on: the Preflight stage
(one login-and-render check, so a half-booted environment fails in a minute
instead of failing every test for the same reason two hours later), the account
lock, and per-lane timeouts so one hung browser cannot eat the build.

## Reading a build

`runLane` maps pytest's exit code onto the build result, so the two kinds of red
are distinguishable:

| Result | Meaning |
| --- | --- |
| **Unstable** | pytest exit 1 — tests failed. Every other lane still ran. Open the report named for the failing lane. |
| **Failure at Preflight** | The environment never rendered. The suite did not run. |
| **Failure, "pytest exited N"** | Exit 2/3/4 — the run itself broke (aborted, broken conftest or plugin, bad arguments), not a product defect. |
| **Failure, "collected no tests"** | Exit 5 — the paths or markers selected nothing. See the coverage table above. |

Each lane publishes its own HTML report (`CBSE M1+M5 Report`, `CBSE M2
Report`, …) and its own `junit.xml` under `reports_ci/<lane>/`, kept apart by
the `PYTEST_REPORTS_DIR` environment variable that `conftest.py` reads for
exactly this purpose.

`.env` is written from the `cbse-smoke-env` credential at the start of every
build and deleted in `post { cleanup }`, along with `screenshots/` and
`tmp_uploads/` — the archive step has already taken that build's copy.
