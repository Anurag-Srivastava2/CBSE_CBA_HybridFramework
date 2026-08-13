# Jenkins post-deployment smoke gate

The [Jenkinsfile](../Jenkinsfile) at the repo root runs the cross-module smoke
suite (16 checks across M1-M5) against a freshly deployed environment. This
page covers what the agent needs, how credentials are supplied, and how the
deployment job triggers it.

## 1. Agent prerequisites

The suite drives real browsers, so the agent needs more than Python:

| Requirement | Notes |
| --- | --- |
| Python 3.12+ | `python3 -m venv` must work |
| Google Chrome | `webdriver-manager` downloads the matching chromedriver at runtime, so chromedriver itself need not be installed |
| Network access to the portal | Both the deployed environment and `googlechromelabs.storage.googleapis.com` for the driver download |
| ~2 GB free disk | Ten concurrent headless Chrome instances plus screenshots |

Label the agent (for example `selenium`) and change `agent any` to
`agent { label 'selenium' }` if only some agents qualify.

On a Windows agent, replace the `sh` steps with `bat`/`powershell` and
`.venv/bin/activate` with `.venv\Scripts\activate`.

## 2. Credentials

The suite reads every account from environment variables — never from
committed files. `.env` is gitignored precisely so credentials stay out of the
repo, and the pipeline must preserve that.

Create a **Secret file** credential in Jenkins holding a complete `.env`
(use [.env.example](../.env.example) as the shape), then bind it in the
`Smoke` stage:

```groovy
environment {
    CBSE_ENV_FILE = credentials('cbse-smoke-env')
}
```

and copy it into place before pytest runs:

```groovy
sh 'cp "$CBSE_ENV_FILE" .env'
```

`utilities/read_config.py` loads `.env` via `os.environ.setdefault`, so real
environment variables always win over the file — either mechanism works.

The alternative is individual **Secret text** credentials:

```groovy
environment {
    CBSE_ALL_USERS_PASSWORD = credentials('cbse-all-users-password')
    CBSE_TEACHER_PASSWORD   = credentials('cbse-teacher-password')
}
```

Usernames (`CBSE_ADMIN_USERNAMES`, `CBSE_SME_USERNAMES`, …) are not secret and
can be set as plain environment variables or job parameters, but keep every
password in Jenkins credentials.

> Do not commit a populated `.env`. If one is ever pushed, rotate every
> account in it — git history preserves the file even after deletion.

## 3. Triggering after each deployment

### Option A — downstream of the deploy job (recommended)

Add to the end of the deployment pipeline:

```groovy
build job: 'cbse-smoke',
      parameters: [string(name: 'CBSE_BASE_URL', value: env.DEPLOYED_URL)],
      wait: true,          // fail the deploy when smoke fails
      propagate: true
```

`wait: true` with `propagate: true` makes the deployment itself go red on a
smoke failure, which is the point of a gate. Use `wait: false` if the deploy
should only *notify*.

### Option B — remote trigger by token

For a deployer outside Jenkins (a shell script, Argo, a cloud pipeline), set
"Trigger builds remotely" on the job with a token, then:

```bash
curl -X POST \
  "https://jenkins.example/job/cbse-smoke/buildWithParameters?token=SMOKE_TOKEN" \
  --data-urlencode "CBSE_BASE_URL=https://your-deployed-env/" \
  --user "$JENKINS_USER:$JENKINS_API_TOKEN"
```

### Option C — on push (regression cover, not a deployment gate)

A GitHub webhook to `https://jenkins.example/github-webhook/` plus
`triggers { githubPush() }` runs the suite whenever the tests themselves
change. Useful, but it validates the suite rather than a deployment.

## 4. What a red build means

| Result | Meaning |
| --- | --- |
| **Failure at Preflight** | The environment never rendered — the deployment is bad or still booting. The suite did not run. |
| **Unstable / test failures** | A specific module's critical path is broken. Open the *CBSE Smoke Report* artifact and read the failing module. |
| **`xfailed`** | A known gap, not a regression. Currently: M3 Item Testing (KI-M3-ITM-001) always xfails, and a reviewer queue xfails when no item set is assigned (KI-M1-QUEUE-001). See [known_issues.md](known_issues.md). |

The `Preflight` stage exists because a half-booted environment fails all 16
checks for one reason and buries the real signal. One cheap login tells you
whether it is worth running the rest.

## 5. Two things to decide before enabling

**The Excel check writes.** `test_smoke_m1_04_excel_upload_creates_item_set`
mints a real item set that lands in the RWG review queue — every build leaves
one behind. On a shared environment that accumulates. Set the
`SKIP_WRITE_CHECKS` parameter to drop it, accepting that bulk ingestion then
goes unverified.

**The vendored template can go stale.**
`data/upload_templates/sme_sheet.xlsx` is a committed copy of the SME upload
template, because a Jenkins agent has no `~/Downloads`. If the application
starts rejecting it after a template version change (see KI-M1-TEMPLATE-003),
re-download the template from the app and replace that file.

## 6. Concurrency

`disableConcurrentBuilds()` is set deliberately. The portal allows one active
session per account and the suite pins each check to a specific account, so
two simultaneous builds would sign each other out and produce failures that
look like product defects. If you need parallel environment testing, give each
environment its own set of accounts rather than removing that option.
