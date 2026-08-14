# Jenkins pipelines

Three pipeline definitions live in the repo root. They share their steps
through [ci/jenkins/cbse.groovy](../ci/jenkins/cbse.groovy), which each one
`load`s after `checkout scm`.

| File | Job | Runs | Typical time |
| --- | --- | --- | --- |
| [Jenkinsfile](../Jenkinsfile) | `cbse-smoke` | 15 critical-path checks across M1–M5 | ~15 min |
| [Jenkinsfile.module](../Jenkinsfile.module) | `cbse-M1` … `cbse-M5` | one module | minutes to ~2 h |
| [Jenkinsfile.full](../Jenkinsfile.full) | `cbse-full` | all 257 tests, in parallel lanes | bounded by the M1+M5 lane |

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
| `cbse-full` | `Jenkinsfile.full` | schedule it nightly, or trigger by hand |

Build each module job once so Jenkins records its parameters, then set the
per-job default by editing `MODULE` in the job configuration. (A single job
with `MODULE` chosen at build time also works, but five jobs give five
independent build histories and trend graphs, which is usually what you want.)

Plugins: **AnsiColor**, **HTML Publisher**, **JUnit** (all already required by
the smoke gate) plus **Lockable Resources** for the account lock below.

## Where the parallelism comes from

Two layers, and the difference matters:

**Inside a pytest process**, `pytest-xdist` with `--dist loadgroup` spreads
tests across workers while keeping every `xdist_group` on a single worker. The
suite uses those groups to encode account ownership — per-account groups plus
one global `serial` group — so this scheduler is what stops two workers signing
each other out of the same portal account. `--dist loadgroup` is not a tuning
choice; any other scheduler breaks the suite.

**Across pytest processes**, `Jenkinsfile.full` runs four lanes at once. The
lanes are drawn along *account* boundaries rather than directory boundaries,
because several modules share accounts:

| Lane | Paths | Accounts | Tests |
| --- | --- | --- | --- |
| Logic | `tests/test_qar_retry_flow.py`, `tests/test_manual_typology_coverage.py` | none — pure Python | 15 |
| M2 | `tests/M2_Web_Portal_Admin` minus `serial` | admin, admin2 | 72 |
| M3 + M4 | `tests/M3_Item_Testing`, `tests/M4_QP_Creation` | teacher2 | 6 |
| M1 + M5 | `tests/M1_Item_Bank_Mgmt`, `tests/M5_Teacher_Contribution`, `tests/_unit` | SME pool, teacher, RWG/SR-RWG/PIT | 159 |
| *(tail)* M2 serial | `tests/M2_Web_Portal_Admin` `serial` only | admin + RWG | 5 |

Three consequences worth knowing before you edit the lanes:

- **M1, M5 and `tests/_unit` must share one process.** All three drive the
  RWG/SR-RWG/PIT reviewer pool, and they share `tmp_uploads/`. In one process
  xdist's global `serial` group covers all of them at once; split into separate
  processes, each keeps its own serial worker and they double-book the
  reviewers. Splitting M1 from M5 does not make the build faster, it makes it
  flaky.
- **`tests/_unit` is misnamed.** 14 of its 22 files drive a real browser
  against SME2 and the reviewer accounts. Only 8 are genuinely browser-free.
  That is why it sits in the M1 lane rather than the Logic lane.
- **M2's `serial` tests run last, alone.** One of them deactivates every RWG
  account to prove that assignments get reassigned, restoring them in a
  `finally`. Running that while M1 and M5 hold reviewer sessions fails them for
  a reason that is not a product defect.

The M1+M5 lane is the critical path; everything else finishes underneath it. So
`WORKERS` is the parameter that decides how long a full build takes, and real
extra parallelism needs **more accounts**, not more lanes — see
[jenkins_setup.md](jenkins_setup.md) section 6.

### Coverage

The lanes are an exact cover: 257 tests, no test in two lanes, none in none.
The module jobs are the same 257 split a different way, which is why M1 also
owns `tests/_unit` and the two pure-Python files:

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

Shared by both new pipelines:

| Parameter | Default | Notes |
| --- | --- | --- |
| `CBSE_BASE_URL` | QA | Environment under test. |
| `WORKERS` | `4` | xdist workers. Each drives a headless Chrome (~200 MB). Above 6 the QA environment has shown connection contention. In `cbse-full` this applies to the M1+M5 lane, the critical path. |
| `RERUNS` | `0` | See below. |
| `ACCOUNT_LOCK` | `cbse-cba-accounts` | Lockable resource name. |

`Jenkinsfile.module` adds `MODULE` (M1–M5) and `SUITE`
(`regression` / `smoke` / `nightly`). `Jenkinsfile.full` adds `LIGHT_WORKERS`
(workers for the M2 and M3+M4 lanes; peak browsers is
`WORKERS + 2 × LIGHT_WORKERS`) and `INCLUDE_NIGHTLY`.

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
