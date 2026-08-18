"""Shared element surveys for the M1 Item Bank Management suites.

M1 drives the SME account across three screens — the manual authoring form,
the bulk upload step, and the My Item Set listing — and several suites visit
more than one of them, so the surveys live here rather than in each test class.

One `ElementChecks` is used per *test*, not per screen: `conftest` collapses a
test's properties with `dict()`, so a second `publish()` would silently replace
the first element table. `enter_screen()` re-points the same collector at the
next screen and photographs it, keeping every row correctly attributed while
still producing one screenshot per page visited.

Not named `test_*`, so pytest does not collect it.
"""

# Every absent element costs its full timeout, and these surveys run 25-60
# checks against elements that all paint together.
CHECK_TIMEOUT = 2


def enter_screen(checks, page_name):
    """Point an existing collector at the next screen and photograph it."""
    checks.page_name = page_name
    checks.capture_page_evidence(page_name)
    return checks


def survey_chrome(checks, page):
    """Application chrome as the SME sees it.

    The SME sidebar is deliberately not the teacher's: no QP Builder, My QP or
    Sets — it carries Repository and Item instead. Surveying it with the
    teacher's list would file FAILED rows for destinations this role is
    correctly not offered.
    """
    checks.check("Header bar", page.HEADER, timeout=CHECK_TIMEOUT)
    checks.check("Sidebar nav", page.SIDEBAR_NAV, timeout=CHECK_TIMEOUT)
    checks.check("Sidebar toggle", page.SIDEBAR_TOGGLE, timeout=CHECK_TIMEOUT)
    checks.check("Notification bell", page.NOTIFICATION_BELL, timeout=CHECK_TIMEOUT)
    checks.check("Theme picker", page.THEME_PICKER, timeout=CHECK_TIMEOUT)
    checks.check("Screen-reader toggle", page.SCREEN_READER_TOGGLE, timeout=CHECK_TIMEOUT)
    checks.check("Language — EN", page.LANG_EN, timeout=CHECK_TIMEOUT)
    checks.check("Language — हिंदी", page.LANG_HI, timeout=CHECK_TIMEOUT)

    missing_nav = checks.safe_call(
        lambda: page.missing_from(page.SME_NAV_ITEMS, page.sme_nav_locator)
    )
    for label in page.SME_NAV_ITEMS:
        checks.check_condition(f"Nav — {label}", label not in missing_nav)
    return checks


def survey_manual_form(checks, page):
    """The SME manual authoring form.

    Excludes the per-item Edit/Delete/Show-answer controls: those are revealed
    by interacting with a staged item card, so recording their absence on
    arrival would report a gap the page is right not to show.
    """
    checks.check("Workspace title", page.WORKSPACE_TITLE, timeout=CHECK_TIMEOUT)
    checks.check("Section — Metadata Tags", page.METADATA_HEADING, timeout=CHECK_TIMEOUT)

    missing_metadata = checks.safe_call(page.missing_metadata_fields)
    for label in page.METADATA_FIELD_LABELS:
        checks.check_condition(f"Field — {label}", label not in missing_metadata)

    missing_content = checks.safe_call(page.missing_content_fields)
    for label in page.CONTENT_FIELD_LABELS:
        checks.check_condition(f"Field — {label}", label not in missing_content)

    dropdowns = checks.safe_call(lambda: page.count_visible(page.METADATA_DROPDOWNS), 0)
    checks.check_condition(
        "Metadata dropdowns rendered",
        dropdowns >= len(page.METADATA_FIELD_LABELS),
        detail=f"{dropdowns} comboboxes visible",
    )

    checks.check("Button — Clear Form", page.CLEAR_FORM_BUTTON, timeout=CHECK_TIMEOUT)
    checks.check("Button — Add Item", page.ADD_ITEM_BUTTON, timeout=CHECK_TIMEOUT)
    checks.check("Answer key textbox", page.ANSWER_KEY_TEXTBOX, timeout=CHECK_TIMEOUT)
    checks.check("Added Items heading", page.ADDED_ITEMS_HEADING, timeout=CHECK_TIMEOUT)

    editors = checks.safe_call(lambda: page.count_visible(page.EDITOR_SURFACES), 0)
    checks.check_condition(
        "Rich-text editors rendered",
        editors >= 2,
        detail=f"{editors} editor surfaces visible",
    )
    toolbar = checks.safe_call(lambda: page.count_visible(page.EDITOR_TOOLBAR_BUTTONS), 0)
    checks.check_condition(
        "Editor toolbar rendered",
        toolbar >= 20,
        detail=f"{toolbar} toolbar buttons visible",
    )

    missing_steps = checks.safe_call(page.missing_manual_wizard_steps)
    for label in page.MANUAL_WIZARD_STEP_LABELS:
        checks.check_condition(f"Wizard step — {label}", label not in missing_steps)
    return checks


def survey_typology_inventory(checks, page):
    """Record which manual typologies the live dropdown offers.

    Recorded softly and *in addition to* the suite's own inventory assertion
    and its KI-M1-TYPOLOGY-001 xfail guard, never in place of them — the guard
    still decides the test outcome.
    """
    options = checks.safe_call(page.get_manual_item_typology_options, ())
    canonical = {
        page.canonical_manual_typology(option)
        for option in options
        if page.canonical_manual_typology(option)
    }
    for typology in page.SUPPORTED_MANUAL_ITEM_TYPOLOGIES:
        checks.check_condition(
            f"Typology — {typology}",
            typology in canonical,
            detail="" if typology in canonical else f"live options: {list(options)}",
        )
    return checks


def survey_upload_step(checks, page, wait_for_history=True):
    """The bulk Upload Item File step and its Previously Uploaded Files table."""
    checks.check("Workspace title", page.WORKSPACE_TITLE, timeout=CHECK_TIMEOUT)
    checks.check(
        "Section — Upload Documents",
        page.UPLOAD_DOCUMENTS_HEADING,
        timeout=CHECK_TIMEOUT,
    )
    checks.check("Drag and drop zone", page.DROPZONE, timeout=CHECK_TIMEOUT)
    checks.check(
        "Button — Add items Individually",
        page.ADD_ITEMS_INDIVIDUALLY_BTN,
        timeout=CHECK_TIMEOUT,
    )
    checks.check(
        "Section — Upload Prerequisites",
        page.PREREQUISITES_HEADING,
        timeout=CHECK_TIMEOUT,
    )

    # Hidden behind the Browse control by design, so presence — not visibility.
    file_inputs = checks.safe_call(
        lambda: len(page.driver.find_elements(*page.FILE_INPUT)), 0
    )
    checks.check_condition(
        "File input present (visually hidden by design)",
        file_inputs,
        detail=f"{file_inputs} file inputs in the DOM",
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

    if not wait_for_history:
        return checks

    checks.check(
        "Section — Previously Uploaded Files",
        page.UPLOAD_HISTORY_HEADING,
        timeout=CHECK_TIMEOUT,
    )
    history_loaded = checks.safe_call(
        lambda: page.wait_for_upload_history(timeout=60), False
    )
    checks.check_condition(
        "Upload history finished loading",
        history_loaded,
        detail="still showing the loading placeholder" if not history_loaded else "",
    )
    missing_columns = checks.safe_call(page.missing_upload_history_columns)
    headers = checks.safe_call(page.get_upload_history_headers)
    for column in page.UPLOAD_HISTORY_COLUMNS:
        checks.check_condition(
            f"Column — {column}",
            column not in missing_columns,
            detail=f"found: {headers}" if column in missing_columns else "",
        )
    rows = checks.safe_call(page.get_upload_history_row_count, 0)
    checks.check_condition(
        "Upload history has rows", rows, detail=f"{rows} rows"
    )
    return checks


def survey_review_queue(checks, page):
    """A reviewer's Review Queue: header, filters, stage tabs, grid.

    Read-only. Reviewer votes are one-time workflow actions per item set, so
    nothing here marks criteria or submits a review — only the tabs are driven,
    and those merely re-scope the listing.
    """
    loaded = checks.safe_call(lambda: page.wait_for_queue_to_load(timeout=60), False)
    checks.check_condition(
        "Review queue finished loading",
        loaded,
        detail="still on the loading placeholder" if not loaded else "",
    )

    checks.check("Review Queue heading", page.QUEUE_PAGE_HEADING, timeout=CHECK_TIMEOUT)
    checks.check("Queue subtitle", page.QUEUE_SUBTITLE, timeout=CHECK_TIMEOUT)
    checks.check("Search box", page.SEARCH_INPUT, timeout=CHECK_TIMEOUT)
    checks.check("Queue table", page.QUEUE_TABLE, timeout=CHECK_TIMEOUT)

    missing_filters = checks.safe_call(
        lambda: page.missing_from(page.QUEUE_FILTER_LABELS, page.queue_filter_locator)
    )
    for label in page.QUEUE_FILTER_LABELS:
        checks.check_condition(f"Filter — {label}", label not in missing_filters)

    missing_tabs = checks.safe_call(
        lambda: page.missing_from(page.QUEUE_TAB_LABELS, page.queue_tab_locator)
    )
    for label in page.QUEUE_TAB_LABELS:
        checks.check_condition(f"Tab — {label}", label not in missing_tabs)

    missing_columns = checks.safe_call(page.missing_queue_columns)
    headers = checks.safe_call(lambda: page.get_headers_text(page.QUEUE_TABLE_HEADERS))
    for column in page.QUEUE_COLUMNS:
        checks.check_condition(
            f"Column — {column}",
            column not in missing_columns,
            detail=f"found: {headers}" if column in missing_columns else "",
        )

    # An empty queue is legitimate workflow state, not a rendering gap, so the
    # row count is recorded as evidence rather than required to be non-zero.
    rows = checks.safe_call(page.get_queue_row_count, 0)
    checks.check_condition(
        "Queue row count recorded",
        True,
        detail=f"{rows} item set(s) waiting" if rows else "queue is empty right now",
    )

    checks.check("Rows per page control", page.ROWS_PER_PAGE, timeout=CHECK_TIMEOUT)
    checks.check("Previous page button", page.PREV_PAGE_BTN, timeout=CHECK_TIMEOUT)
    checks.check("Next page button", page.NEXT_PAGE_BTN, timeout=CHECK_TIMEOUT)
    return checks


def survey_reviewer_chrome(checks, page):
    """Chrome as a reviewer sees it — a shorter sidebar than SME or teacher."""
    checks.check("Header bar", page.HEADER, timeout=CHECK_TIMEOUT)
    checks.check("Sidebar nav", page.SIDEBAR_NAV, timeout=CHECK_TIMEOUT)
    checks.check("Sidebar toggle", page.SIDEBAR_TOGGLE, timeout=CHECK_TIMEOUT)
    checks.check("Notification bell", page.NOTIFICATION_BELL, timeout=CHECK_TIMEOUT)
    checks.check("Theme picker", page.THEME_PICKER, timeout=CHECK_TIMEOUT)
    checks.check("Screen-reader toggle", page.SCREEN_READER_TOGGLE, timeout=CHECK_TIMEOUT)
    checks.check("Language — EN", page.LANG_EN, timeout=CHECK_TIMEOUT)
    checks.check("Language — हिंदी", page.LANG_HI, timeout=CHECK_TIMEOUT)

    missing_nav = checks.safe_call(
        lambda: page.missing_from(page.REVIEWER_NAV_ITEMS, page.reviewer_nav_locator)
    )
    for label in page.REVIEWER_NAV_ITEMS:
        checks.check_condition(f"Nav — {label}", label not in missing_nav)
    return checks


def survey_opened_item_set(checks, page):
    """An opened review item set: title, stage filters, item grid, QAR report.

    Read-only — no criteria are marked and no review is submitted.
    """
    checks.check("Item set title", page.ITEM_SET_TITLE, timeout=CHECK_TIMEOUT)
    checks.check("Button — Back", page.ITEM_SET_BACK_BUTTON, timeout=CHECK_TIMEOUT)
    checks.check(
        "Button — Download QAR Report",
        page.DOWNLOAD_QAR_REPORT_BUTTON,
        timeout=CHECK_TIMEOUT,
    )
    checks.check("Item table", page.ITEM_SET_ITEM_TABLE, timeout=CHECK_TIMEOUT)

    missing_filters = checks.safe_call(
        lambda: page.missing_from(page.ITEM_SET_FILTER_LABELS, page.queue_filter_locator)
    )
    for label in page.ITEM_SET_FILTER_LABELS:
        checks.check_condition(f"Filter — {label}", label not in missing_filters)

    missing_tabs = checks.safe_call(
        lambda: page.missing_from(page.ITEM_SET_REVIEW_TAB_LABELS, page.queue_tab_locator)
    )
    for label in page.ITEM_SET_REVIEW_TAB_LABELS:
        checks.check_condition(f"Review tab — {label}", label not in missing_tabs)

    missing_columns = checks.safe_call(page.missing_item_set_item_columns)
    headers = checks.safe_call(lambda: page.get_headers_text(page.ITEM_SET_ITEM_HEADERS))
    for column in page.ITEM_SET_ITEM_COLUMNS:
        checks.check_condition(
            f"Column — {column}",
            column not in missing_columns,
            detail=f"found: {headers}" if column in missing_columns else "",
        )

    rows = checks.safe_call(page.get_item_set_item_row_count, 0)
    checks.check_condition("Item set lists items", rows, detail=f"{rows} item(s)")
    return checks


def survey_item_sets(checks, page):
    """The My Item Set listing: header, filters, review-stage tabs, grid."""
    checks.check("My Item Set heading", page.ITEM_SETS_HEADING, timeout=CHECK_TIMEOUT)
    checks.check("Listing subtitle", page.ITEM_SETS_SUBTITLE, timeout=CHECK_TIMEOUT)
    checks.check("Search box", page.ITEM_SET_SEARCH_INPUT, timeout=CHECK_TIMEOUT)
    checks.check("Tab list", page.ITEM_SET_TAB_LIST, timeout=CHECK_TIMEOUT)

    missing_filters = checks.safe_call(
        lambda: page.missing_from(page.ITEM_SET_FILTER_LABELS, page.item_set_filter_locator)
    )
    for label in page.ITEM_SET_FILTER_LABELS:
        checks.check_condition(f"Filter — {label}", label not in missing_filters)

    missing_tabs = checks.safe_call(
        lambda: page.missing_from(page.ITEM_SET_TAB_LABELS, page.item_set_tab_locator)
    )
    for label in page.ITEM_SET_TAB_LABELS:
        checks.check_condition(f"Tab — {label}", label not in missing_tabs)

    missing_columns = checks.safe_call(page.missing_item_set_columns)
    headers = checks.safe_call(page.get_item_set_table_headers)
    for column in page.ITEM_SET_COLUMNS:
        checks.check_condition(
            f"Column — {column}",
            column not in missing_columns,
            detail=f"found: {headers}" if column in missing_columns else "",
        )

    rows = checks.safe_call(page.get_item_set_row_count, 0)
    checks.check_condition("Listing rendered rows", rows, detail=f"{rows} rows")

    checks.check("Rows per page control", page.ITEM_SET_ROWS_PER_PAGE, timeout=CHECK_TIMEOUT)
    checks.check("Previous page button", page.ITEM_SET_PREV_PAGE, timeout=CHECK_TIMEOUT)
    checks.check("Next page button", page.ITEM_SET_NEXT_PAGE, timeout=CHECK_TIMEOUT)
    return checks
