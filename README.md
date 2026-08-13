# CBSE_CBA

This framework was created from your BlazeMeter Selenium YAML recordings.

## Flow covered

### Teacher login
1. Open CBSE dev URL
2. Enter teacher username
3. Enter password
4. Click Sign In
5. Verify dashboard page

### SME manual item creation
1. Open CBSE dev URL
2. Login as SME
3. Open item/manual creation area
4. Select True/False manual item type
5. Enter question
6. Select answer
7. Enter explanation
8. Click Add Item
9. Continue
10. Submit Set for QAR

## Important

Copy `.env.example` to `.env`, then set the local URL and credentials:

```text
.env
```

Set:

```dotenv
CBSE_BASE_URL=https://your-environment.example/
CBSE_TEACHER_USERNAME=your_teacher_email
CBSE_TEACHER_PASSWORD=your_teacher_password
CBSE_SME_USERNAME=your_sme_email
CBSE_ALL_USERS_PASSWORD=your_shared_test_password
```

You can also update manual item data:

```ini
[manual_item]
question_text = Is 51 > 4?
explanation = Yes, 51 is greater than 4.
answer = True
```

## Setup

Open terminal from project root and run:

```bash
pip install -r requirements.txt
```

## Run all tests

```bash
pytest
```

## Run one Excel module

```bash
pytest tests/M1_Item_Bank_Mgmt
```

## Run the smoke suite

```bash
pytest -m smoke -n 4 --dist loadgroup
```

A single critical-path pass across all five modules — twelve checks that answer
"is this build worth running the full suite against?" in a few minutes:

| Module | Account | Checks |
| --- | --- | --- |
| M1 - Item Bank Mgmt | SME | Item-creation workspace opens; manual form renders its typology list and Add Item; bulk upload reaches the Upload Documents step; **an Excel workbook uploads and mints an item set** |
| M2 - Web Portal Admin | Admin | Dashboard KPI cards hold numbers; Item Bank Overview renders its columns; User Management lists accounts |
| M3 - Item Testing | Admin | Probes for the IRT/ICC/DIF workspace — currently `xfailed` as KI-M3-ITM-001 |
| M4 - QP Creation | teacher2 | QP Builder reaches Assessment Configuration with Manual + Automated modes; My QP listing opens |
| M5 - Teacher Contribution | Primary teacher | Login lands on the dashboard and item creation opens; upload history table renders |

All checks are read-only **except** the M1 Excel ingestion check, which
uploads a generated 2-item workbook and submits it. That mints a real item set
which enters the RWG review queue, so **each smoke run leaves one item set
behind**. Everything else creates, edits and deletes nothing, so the rest of
the suite is safe to re-run anywhere without seeding or cleanup.

To run the read-only subset only — for example against a shared or
pre-release environment where the extra sets are unwelcome:

```bash
pytest -m smoke -k "not excel_upload_creates_item_set" -n 4 --dist loadgroup
```

Each module drives its own account and carries an `xdist_group`, because the
portal keeps one active session per account — always pass `--dist loadgroup`
when running it with `-n`.

Files are named `test_smoke_*.py` and live in their module folder, so they
group correctly in the Extent report. The `smoke` marker is applied
automatically from that name.

## Run in parallel

```bash
pytest tests/M5_Teacher_Contribution -n 4 --dist loadgroup
```

Use `--dist loadgroup`: tests marked `serial` share an xdist group, so they all
land on one worker instead of running alongside each other. Several end-to-end
flows drive the same application accounts (contributor, app-assigned RWG
reviewer, PIT panel), and the portal keeps one active session per account, so
running two of them at once signs each out of the other's session.

## Run headless

```bash
CBSE_HEADLESS=1 pytest tests/M5_Teacher_Contribution -n 4 --dist loadgroup
```

Set `CBSE_HEADLESS` to `1`/`true`/`yes` (PowerShell: `$env:CBSE_HEADLESS = "1"`).

## Project structure

```text
pages/
  common/     Shared POM classes such as BasePage and LoginPage
  teacher/    Teacher-specific page objects
  sme/        SME-specific page objects
  rwg/        RWG-specific page objects

tests/
  M1_Item_Bank_Mgmt/          M1 - Item Bank Mgmt
  M2_Web_Portal_Admin/        M2 - Web Portal Admin
  M3_Item_Testing/            M3 - Item Testing
  M4_QP_Creation/             M4 - QP Creation
  M5_Teacher_Contribution/    M5 - Teacher Contribution

rtm/           Excel RTM manifest and traceability checks
```

Run the RTM validation separately with `pytest rtm`.

## Run with HTML report

```bash
pytest -v -s --html=reports/report.html --self-contained-html
```

## Output

- HTML report: `reports/report.html`
- Logs: `logs/automation_YYYY_MM_DD.log`
- Failure screenshots: `screenshots/`

## Expected failures

`xfailed` in pytest/report output means a known product, test-data, or environment gap was hit intentionally. Track these in [docs/known_issues.md](docs/known_issues.md). When the product behavior or fixture data is ready, remove the related `pytest.xfail(...)` and keep the assertion as a normal test.

## Locator notes

Useful locators extracted from BlazeMeter SME recording:

- Sign In button: `//button[@type='submit' and normalize-space()='Sign In']`
- Item creation sidebar icon: `.lucide-pen-line`
- Item content editor: `[aria-label='itemContent'] .tiptap`
- True button: `//button[@type='button' and normalize-space()='True']`
- Explanation editor: `[aria-label='explanation'] .tiptap`
- Add Item: `//button[contains(normalize-space(),'Add Item')]`
- Continue: `//button[contains(normalize-space(),'Continue')]`
- Submit Set for QAR: `//button[contains(normalize-space(),'Submit Set for QAR')]`

The recording had noisy clicks and one accidental YouTube navigation. Those were intentionally excluded.

## Extent report auto-open

After a pytest run, the framework writes and opens:

```text
reports/extent_report.html
```

Auto-open is controlled from `config/config.ini`:

```ini
[reports]
auto_open_extent = true
```

Set it to `false` to generate the report without opening a browser. Allure-compatible
JSON results are still written to `reports/allure-results`, but Allure is not auto-opened.
