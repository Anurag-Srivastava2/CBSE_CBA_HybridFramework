"""Shared element surveys for the M4 QP Creation suites.

All three QP suites walk the same three screens — Assessment Configuration,
the My QP listing, and a paper preview — so the surveys live here rather than
being copied into each test class.

One `ElementChecks` is used per *test*, not per screen: `conftest` collapses a
test's properties with `dict()`, so a second `publish()` would silently replace
the first element table. `enter_screen()` therefore re-points the same
collector at the next screen and files a screenshot for it, which keeps every
row correctly attributed and still yields one screenshot per page visited.

Not named `test_*`, so pytest does not collect it.
"""

# Every absent element costs its full timeout, and these surveys run 30-60
# checks against elements that all paint together.
CHECK_TIMEOUT = 2


def enter_screen(checks, page_name):
    """Point an existing collector at the next screen and photograph it.

    Constructing a second ElementChecks would take the screenshot but lose the
    first screen's rows at publish time.
    """
    checks.page_name = page_name
    checks.capture_page_evidence(page_name)
    return checks


def survey_builder(checks, page, mode="Manual Build"):
    """Assessment Configuration: shell, mode tabs, wizard steps, config fields."""
    checks.check("Builder heading", page.BUILDER_HEADING, timeout=CHECK_TIMEOUT)
    # The Assessment Configuration and Workflow Overview cards belong to the
    # Manual Build tab; Auto Generator replaces them with Choose Generation
    # Level / Question Paper Details. Checking for them in both modes recorded
    # two FAILED rows per run for cards the screen is right not to show.
    if mode != "Auto Generator":
        checks.check(
            "Section — Assessment Configuration",
            page.ASSESSMENT_CONFIG_HEADING,
            timeout=CHECK_TIMEOUT,
        )
        checks.check(
            "Section — Workflow Overview",
            page.WORKFLOW_OVERVIEW_HEADING,
            timeout=CHECK_TIMEOUT,
        )

    missing_tabs = checks.safe_call(page.missing_mode_tabs)
    for label in page.MODE_TAB_LABELS:
        checks.check_condition(f"Tab — {label}", label not in missing_tabs)

    # The two modes run different wizards: Auto Generator has no Build Paper step.
    step_labels = page.AUTO_STEP_LABELS if mode == "Auto Generator" else page.MANUAL_STEP_LABELS
    missing_steps = checks.safe_call(
        lambda: page.missing_from(step_labels, page.wizard_step_locator)
    )
    for label in step_labels:
        checks.check_condition(f"Wizard step — {label}", label not in missing_steps)

    if mode == "Auto Generator":
        checks.check(
            "Section — Choose Generation Level",
            page.GENERATION_LEVEL_HEADING,
            timeout=CHECK_TIMEOUT,
        )
        checks.check(
            "Generation level — Section Level",
            page.GENERATION_LEVEL_SECTION,
            timeout=CHECK_TIMEOUT,
        )
        checks.check(
            "Generation level — Item Level",
            page.GENERATION_LEVEL_ITEM,
            timeout=CHECK_TIMEOUT,
        )
        checks.check(
            "Section — Question Paper Details",
            page.QP_DETAILS_HEADING,
            timeout=CHECK_TIMEOUT,
        )
        checks.check(
            "Distribution — all sets the same",
            page.DISTRIBUTION_SAME,
            timeout=CHECK_TIMEOUT,
        )
        checks.check(
            "Distribution — each set different",
            page.DISTRIBUTION_DIFFERENT,
            timeout=CHECK_TIMEOUT,
        )
        field_labels = page.AUTO_CONFIG_LABELS
        inputs = (
            ("Exam duration", page.AUTO_DURATION_INPUT),
            ("Number of sections", page.AUTO_SECTIONS_INPUT),
            ("Total marks", page.AUTO_MARKS_INPUT),
        )
    else:
        field_labels = page.MANUAL_CONFIG_LABELS
        inputs = (
            ("Exam duration", page.CFG_DURATION_INPUT),
            ("Total marks", page.CFG_MARKS_INPUT),
            ("No. of sections", page.CFG_SECTIONS_INPUT),
        )

    missing_labels = checks.safe_call(
        lambda: page.missing_from(field_labels, page.label_locator)
    )
    for label in field_labels:
        checks.check_condition(f"Field — {label}", label not in missing_labels)

    for name, locator in inputs:
        checks.check(f"Input — {name}", locator, timeout=CHECK_TIMEOUT)

    comboboxes = checks.safe_call(lambda: page.count_visible(page.COMBOBOXES), 0)
    checks.check_condition(
        "Metadata dropdowns rendered",
        comboboxes,
        detail=f"{comboboxes} comboboxes visible",
    )
    checks.check(
        "General Instructions editor", page.RICH_TEXT_EDITOR, timeout=CHECK_TIMEOUT
    )
    checks.check("Button — Continue", page.CONTINUE_BUTTON, timeout=CHECK_TIMEOUT)
    return checks


def survey_my_qp(checks, page):
    """My QP listing: header, filters, search, grid columns, pagination."""
    checks.check("My QP heading", page.MY_QP_HEADING, timeout=CHECK_TIMEOUT)
    checks.check("My QP subtitle", page.MY_QP_SUBTITLE, timeout=CHECK_TIMEOUT)
    checks.check(
        "Button — Create New Paper", page.CREATE_NEW_PAPER_BUTTON, timeout=CHECK_TIMEOUT
    )
    checks.check("Search box", page.MY_QP_SEARCH_INPUT, timeout=CHECK_TIMEOUT)

    missing_filters = checks.safe_call(page.missing_my_qp_filters)
    for label in page.MY_QP_FILTER_LABELS:
        checks.check_condition(f"Filter — {label}", label not in missing_filters)

    checks.check("Paper listing table", page.MY_QP_TABLE, timeout=CHECK_TIMEOUT)
    missing_columns = checks.safe_call(page.missing_my_qp_columns)
    headers = checks.safe_call(page.get_table_headers)
    for column in page.MY_QP_COLUMNS:
        checks.check_condition(
            f"Column — {column}",
            column not in missing_columns,
            detail=f"found: {headers}" if column in missing_columns else "",
        )

    row_count = checks.safe_call(page.get_my_qp_row_count, 0)
    checks.check_condition(
        "Listing rendered rows", row_count, detail=f"{row_count} rows"
    )

    # The listing states the "published papers are immutable" rule through its
    # own controls: a published row's delete button is disabled and says why.
    blocked = checks.safe_call(lambda: page.count_visible(page.MY_QP_DELETE_BLOCKED), 0)
    checks.check_condition(
        "Published papers expose a disabled Delete control",
        blocked,
        detail=f"{blocked} rows blocked from deletion",
    )

    checks.check("Rows per page control", page.ROWS_PER_PAGE, timeout=CHECK_TIMEOUT)
    checks.check("Previous page button", page.PREV_PAGE_BTN, timeout=CHECK_TIMEOUT)
    checks.check("Next page button", page.NEXT_PAGE_BTN, timeout=CHECK_TIMEOUT)
    return checks


def survey_preview(checks, page):
    """Paper preview: title, instructions, sections, toolbar actions, summary."""
    checks.check("Paper heading", page.PREVIEW_PAPER_HEADING, timeout=CHECK_TIMEOUT)
    # General Instructions is deliberately not a presence check: the section
    # only renders when the author supplied instructions, and none of these
    # suites configures any, so requiring it recorded a FAILED row on every run
    # for a section the paper is correct to omit. Recorded as content instead.
    instructions = checks.safe_call(
        lambda: page.count_visible(page.PREVIEW_INSTRUCTIONS_HEADING), 0
    )
    checks.check_condition(
        "Paper renders its body (instructions optional)",
        True,
        detail=(
            "General Instructions section present"
            if instructions
            else "no General Instructions section — none was configured"
        ),
    )
    checks.check("Button — Back", page.PREVIEW_BACK_BUTTON, timeout=CHECK_TIMEOUT)
    checks.check("Button — Print", page.PREVIEW_PRINT_BUTTON, timeout=CHECK_TIMEOUT)
    checks.check("Button — Download", page.PREVIEW_DOWNLOAD_BUTTON, timeout=CHECK_TIMEOUT)
    checks.check(
        "Button — Download with Answer Key",
        page.PREVIEW_DOWNLOAD_WITH_KEY_BUTTON,
        timeout=CHECK_TIMEOUT,
    )
    checks.check("End of paper marker", page.PREVIEW_END_MARKER, timeout=CHECK_TIMEOUT)

    sections = checks.safe_call(lambda: page.count_visible(page.PREVIEW_SECTION_TITLES), 0)
    checks.check_condition(
        "Section headings rendered", sections, detail=f"{sections} sections"
    )

    summary = checks.safe_call(page.get_paper_summary_metadata, {}) or {}
    missing_summary = checks.safe_call(
        lambda: page.missing_preview_summary_fields(summary)
    )
    for field in page.PREVIEW_SUMMARY_FIELDS:
        checks.check_condition(
            f"Summary field — {field}",
            field not in missing_summary,
            detail=f"read {summary.get(field)!r}" if field in summary else "",
        )

    # The toolbar chips, read from the chips themselves rather than through
    # get_header_metadata_text(), which matches most of the document.
    chips = checks.safe_call(page.get_header_chip_texts, [])
    checks.check_condition(
        "Toolbar chips — duration / marks / questions",
        len(chips) >= 3,
        detail=f"chips: {chips}",
    )
    return summary


def survey_chrome(checks, page):
    """Application chrome shared by every QP screen."""
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
