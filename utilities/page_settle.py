"""Wait for a page to finish painting, so a screenshot shows it.

Lives apart from both `screenshot_utils` and `page_evidence` because both need
it and importing between them would be circular.
"""
import os
import time

# A settled page clears in two polls (~0.3s). The cap only costs anything on a
# page that never finishes, where the spinner is itself the evidence.
#
# 15s, not 8s: sampled five loads of the sign-in screen and four settled in
# 2.7-3.5s while the fifth needed longer than 8s for the hero artwork alone. An
# 8s cap turned that tail into exactly the half-painted screenshot this wait
# exists to prevent, and the extra budget is only ever spent on a page that is
# genuinely still loading.
POLL_SECONDS = 0.15
DEFAULT_SETTLE_TIMEOUT = 15
# Fonts get their own, shorter budget. On this environment the icon font is
# blocked outright, so `document.fonts.status` sits on 'loading' and the page
# renders ligature names ('mail_outline') where the glyphs belong - a state no
# amount of waiting improves. Measured on the sign-in screen: fonts held the
# shutter ~2s of a ~4s total, on every page.
FONT_GRACE_SECONDS = 1.5
SOFT_REASONS = frozenset({"fonts"})

# Everything below runs in the browser in one round trip, because `find_elements`
# from Python pays the 5s implicit wait on every miss.
#
# `settled` is a verdict, `mark` a fingerprint of what is currently painted. A
# page counts as photographable once it reports settled twice running with the
# same mark - the verdict alone fires between two renders of a list that is still
# filling in.
SETTLE_SCRIPT = """
if (document.readyState !== 'complete') return {settled: false, mark: 'readyState'};

const isVisible = (element) => {
    const box = element.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) return false;
    const style = window.getComputedStyle(element);
    return style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
};

// Explicit busy signals the app publishes itself.
for (const element of document.querySelectorAll('[aria-busy="true"], [role="progressbar"]')) {
    if (isVisible(element)) return {settled: false, mark: 'aria-busy'};
}

// This SPA's own convention: a short leaf node reading "Loading ...", which is
// what a screenshot taken too early actually shows ("Loading sign in..."). Leaf
// nodes only, and short ones, so a content row that happens to start with the
// word does not hold the shutter for the full timeout.
for (const element of document.querySelectorAll('div, span, p, h1, h2, h3, h4')) {
    if (element.children.length) continue;
    const text = (element.textContent || '').trim();
    if (text && text.length < 60 && /^loading\\b/i.test(text) && isVisible(element)) {
        return {settled: false, mark: 'loading-text'};
    }
}

// A logo mid-decode photographs as a blank box, so it is not settled either.
for (const image of document.images) {
    if (!image.complete && isVisible(image)) return {settled: false, mark: 'image-decode'};
}

// Hero/banner artwork is a CSS background-image, which never appears in
// document.images - the sign-in screen's login-bg.png lands ~3.4s after the DOM
// is ready, so without this the shot came out with a flat gradient where the
// photograph belongs. Probing a url the page already requested is a cache hit.
const backgroundUrls = new Set();
let inspected = 0;
for (const element of document.querySelectorAll('body, main, header, section, aside, figure, div')) {
    if (inspected++ > 600) break;                 // cost guard: ~16ms at this size
    const value = window.getComputedStyle(element).backgroundImage;
    if (!value || value === 'none') continue;
    const match = /url\\(["']?([^"')]+)["']?\\)/.exec(value);
    if (match) backgroundUrls.add(match[1]);
}
for (const url of backgroundUrls) {
    const probe = new Image();
    probe.src = url;
    if (!probe.complete) return {settled: false, mark: 'background-decode'};
}

// Icon fonts land late; before they do, the page renders ligature names as
// literal text ('mail_outline') exactly where the icon belongs.
if (document.fonts && document.fonts.status !== 'loaded') {
    return {settled: false, mark: 'fonts'};
}

return {
    settled: true,
    mark: [
        document.getElementsByTagName('*').length,
        (document.body ? document.body.innerText.length : 0),
        document.images.length
    ].join(':')
};
"""


def settle_timeout():
    try:
        return float(os.getenv("CBSE_EVIDENCE_SETTLE_TIMEOUT", DEFAULT_SETTLE_TIMEOUT))
    except ValueError:
        return DEFAULT_SETTLE_TIMEOUT


def wait_until_page_settled(driver, timeout=None):
    """Hold until the page looks painted, or the timeout expires. Never raises.

    A survey is built the moment the test reaches a page, while the SPA may still
    be on its global "Loading ..." screen - the checks that follow each wait for
    their element, but the screenshot has no such patience and came out as a
    spinner. Returns True if the page settled, False if the timeout won.
    """
    if timeout is None:
        timeout = settle_timeout()
    started = time.monotonic()
    deadline = started + timeout
    previous_mark = None
    while True:
        try:
            state = driver.execute_script(SETTLE_SCRIPT)
        except Exception:  # noqa: BLE001
            # An alert, a dead session, a cross-origin frame, or a driver-like
            # object with no execute_script: shoot what we have. This must never
            # raise - the shutter is not allowed to fail a test.
            return False
        state = state if isinstance(state, dict) else {}
        mark = state.get("mark")
        if state.get("settled"):
            if mark == previous_mark:
                return True
            previous_mark = mark
        elif mark in SOFT_REASONS and time.monotonic() - started >= FONT_GRACE_SECONDS:
            # Everything else has settled and only a late web font is outstanding.
            # Stop paying for it on every page.
            return True
        else:
            # Reset the streak: a page that goes busy again has to settle afresh.
            previous_mark = None
        if time.monotonic() >= deadline:
            return False
        time.sleep(POLL_SECONDS)
