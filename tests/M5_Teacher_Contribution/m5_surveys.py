"""Shared element surveys for the M5 Teacher Contribution suites.

The teacher dashboard, contribution workspace and upload step are visited by
the smoke checks, the login checks and the end-to-end chains alike, so the
surveys live here rather than inside one test class.

One `ElementChecks` per *test*, re-pointed with `enter_screen()` as the test
moves between screens — two collectors in one test would lose the first table,
because conftest collapses a test's properties with `dict()`. Re-publishing the
*same* collector is safe and is how the long chains keep their rows when a late
phase fails.

Not named `test_*`, so pytest does not collect it.
"""

# Every absent element costs its full timeout, and these surveys run 20-60
# checks against elements that all paint together.
CHECK_TIMEOUT = 2


def enter_screen(checks, page_name):
    """Point an existing collector at the next screen and photograph it."""
    checks.page_name = page_name
    checks.capture_page_evidence(page_name)
    return checks


def survey_teacher_chrome(checks, page):
    """Application chrome as the teacher sees it.

    The teacher sidebar carries QP Builder / My QP / Sets, which the SME's does
    not — surveying a teacher screen with the SME list would file FAILED rows
    for destinations this role is correctly not offered, and vice versa.
    """
    checks.check("Header bar", page.HEADER, timeout=CHECK_TIMEOUT)
    checks.check("Sidebar nav", page.SIDEBAR_NAV, timeout=CHECK_TIMEOUT)
    checks.check("Sidebar toggle", page.SIDEBAR_TOGGLE, timeout=CHECK_TIMEOUT)
    checks.check("Notification bell", page.NOTIFICATION_BELL, timeout=CHECK_TIMEOUT)
    checks.check("Theme picker", page.THEME_PICKER, timeout=CHECK_TIMEOUT)
    checks.check("Screen-reader toggle", page.SCREEN_READER_TOGGLE, timeout=CHECK_TIMEOUT)
    checks.check("Language — EN", page.LANG_EN, timeout=CHECK_TIMEOUT)
    checks.check("Language — हिंदी", page.LANG_HI, timeout=CHECK_TIMEOUT)

    missing_nav = checks.safe_call(page.missing_nav_items)
    for label in page.NAV_ITEMS:
        checks.check_condition(f"Nav — {label}", label not in missing_nav)
    return checks


def survey_teacher_dashboard(checks, dashboard):
    """The teacher landing dashboard: greeting, stat cards, charts, grid."""
    checks.check("Welcome header", dashboard.PAGE_HEADER, timeout=CHECK_TIMEOUT)
    greeting = checks.text_of(dashboard.PAGE_HEADER)
    checks.check_condition(
        "Welcome header greets the user",
        "hello" in greeting.casefold(),
        detail=f"header text: {greeting!r}" if greeting else "no header text",
    )
    checks.check("Page subtitle", dashboard.PAGE_SUBTITLE, timeout=CHECK_TIMEOUT)
    checks.check(
        "Button — Create an Item Set",
        dashboard.CREATE_ITEM_SET_CTA,
        timeout=CHECK_TIMEOUT,
    )

    missing_stats = checks.safe_call(dashboard.missing_stat_cards)
    for label in dashboard.STAT_LABELS:
        checks.check_condition(f"Stat card — {label}", label not in missing_stats)

    missing_charts = checks.safe_call(dashboard.missing_chart_sections)
    for title in dashboard.CHART_TITLES:
        checks.check_condition(f"Section — {title}", title not in missing_charts)

    checks.check(
        "Section — My Item Sets", dashboard.SECTION_MY_ITEM_SETS, timeout=CHECK_TIMEOUT
    )
    checks.check("Item set grid", dashboard.TABLE, timeout=CHECK_TIMEOUT)
    checks.check("Grid tab list", dashboard.TAB_LIST, timeout=CHECK_TIMEOUT)

    missing_tabs = checks.safe_call(dashboard.missing_tabs)
    for label in dashboard.TAB_LABELS:
        checks.check_condition(f"Tab — {label}", label not in missing_tabs)

    missing_columns = checks.safe_call(dashboard.missing_columns)
    headers = checks.safe_call(dashboard.get_table_headers)
    for column in dashboard.ITEM_SET_COLUMNS:
        checks.check_condition(
            f"Column — {column}",
            column not in missing_columns,
            detail=f"found: {headers}" if column in missing_columns else "",
        )

    checks.check("Rows per page control", dashboard.ROWS_PER_PAGE, timeout=CHECK_TIMEOUT)
    checks.check("Previous page button", dashboard.PREV_PAGE_BTN, timeout=CHECK_TIMEOUT)
    checks.check("Next page button", dashboard.NEXT_PAGE_BTN, timeout=CHECK_TIMEOUT)
    return checks


def survey_contribution_workspace(checks, page):
    """The teacher's item-creation workspace (Upload Item File step)."""
    checks.check("Workspace title", page.WORKSPACE_TITLE, timeout=CHECK_TIMEOUT)
    checks.check(
        "Section — Upload Documents",
        page.UPLOAD_DOCUMENTS_HEADING,
        timeout=CHECK_TIMEOUT,
    )
    checks.check("Drag and drop zone", page.DROPZONE, timeout=CHECK_TIMEOUT)
    checks.check(
        "Section — Upload Prerequisites",
        page.PREREQUISITES_HEADING,
        timeout=CHECK_TIMEOUT,
    )

    missing_mode_tabs = checks.safe_call(page.missing_mode_tabs)
    for label in page.MODE_TAB_LABELS:
        checks.check_condition(f"Tab — {label}", label not in missing_mode_tabs)

    missing_steps = checks.safe_call(page.missing_wizard_steps)
    for label in page.WIZARD_STEP_LABELS:
        checks.check_condition(f"Wizard step — {label}", label not in missing_steps)

    missing_prereqs = checks.safe_call(page.missing_prerequisite_tabs)
    for label in page.PREREQUISITE_TAB_LABELS:
        checks.check_condition(f"Prerequisite tab — {label}", label not in missing_prereqs)
    return checks


def survey_upload_history(checks, page):
    """The Previously Uploaded Files table on the upload step."""
    checks.check(
        "Section — Previously Uploaded Files",
        page.UPLOAD_HISTORY_HEADING,
        timeout=CHECK_TIMEOUT,
    )
    loaded = checks.safe_call(lambda: page.wait_for_upload_history(timeout=60), False)
    checks.check_condition(
        "Upload history finished loading",
        loaded,
        detail="still showing the loading placeholder" if not loaded else "",
    )
    missing_columns = checks.safe_call(page.missing_upload_history_columns)
    headers = checks.safe_call(page.get_upload_history_headers)
    for column in page.UPLOAD_HISTORY_COLUMNS:
        checks.check_condition(
            f"Column — {column}",
            column not in missing_columns,
            detail=f"found: {headers}" if column in missing_columns else "",
        )
    # A never-used account legitimately has no rows, so the count is evidence
    # rather than a requirement.
    rows = checks.safe_call(page.get_upload_history_row_count, 0)
    checks.check_condition(
        "Upload history row count recorded",
        True,
        detail=f"{rows} row(s)" if rows else "no upload history yet",
    )
    return checks
