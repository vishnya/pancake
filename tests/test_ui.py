"""Playwright UI tests for the Pancake web interface.

Covers both desktop (1280x720) and mobile iPhone (375x812) viewports.
Run with: .venv/bin/python -m pytest tests/test_ui.py -v
"""

import re

import pytest
from playwright.sync_api import expect

from tests.conftest_ui import (
    server_url,
    seed,
    DESKTOP_VIEWPORT,
    IPHONE_VIEWPORT,
)
from pancake.priorities import Task, ProjectInfo
from ux_checks import (
    check_uniform_sibling_sizing,
    check_touch_targets,
    check_no_horizontal_scroll,
    check_font_readability,
    check_elements_in_viewport,
    check_no_text_overflow,
    check_clickable_not_obscured,
    check_consistent_spacing,
    check_button_uniformity,
    run_all_checks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _navigate(page, url):
    """Navigate to the app and wait for initial render."""
    page.goto(url)
    page.wait_for_selector(".container")


# ---------------------------------------------------------------------------
# 1. test_page_loads
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_page_loads(page, server_url, viewport):
    page.set_viewport_size(viewport)
    _navigate(page, server_url)
    expect(page).to_have_title("Pancake")
    expect(page.locator("#active-section")).to_be_visible()
    expect(page.locator("#next-section")).to_be_visible()
    expect(page.locator("#projects-section")).to_be_visible()
    expect(page.locator("#done-section")).to_be_visible()


# ---------------------------------------------------------------------------
# 2. test_section_counts_update
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_section_counts_update(page, server_url, viewport):
    seed(
        active=[Task(text="a1", project="P"), Task(text="a2", project="P")],
        up_next=[Task(text="n1", project="P")],
        done=[Task(text="d1", project="P", done=True), Task(text="d2", project="P", done=True)],
        projects=[ProjectInfo(name="P")],
    )
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    expect(page.locator(".active-header .section-count")).to_have_text("(2)")
    expect(page.locator(".next-header .section-count")).to_have_text("(1)")
    expect(page.locator(".done-header .section-count")).to_have_text("(2)")


# ---------------------------------------------------------------------------
# 3. test_section_collapse_expand
#    Uses the History/Done section which has a simple toggle via .collapsible-header.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_section_collapse_expand(page, server_url, viewport):
    seed(
        done=[Task(text="done task", project="P", done=True)],
        projects=[ProjectInfo(name="P")],
    )
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    section = page.locator("#done-section")
    header = page.locator(".done-header")
    body = section.locator(".section-body")

    # Initially expanded (not collapsed)
    expect(body).to_be_visible()

    # Click header to collapse
    header.click()
    expect(section).to_have_class(re.compile(r"collapsed"))
    expect(body).to_be_hidden()

    # Click again to expand
    header.click()
    expect(section).not_to_have_class(re.compile(r"collapsed"))
    expect(body).to_be_visible()


# ---------------------------------------------------------------------------
# 4. test_add_task
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_add_task(page, server_url, viewport):
    seed(up_next=[], projects=[ProjectInfo(name="Test")])
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    # Add a task via the JS api() function which also triggers render
    page.evaluate("""async () => {
        await api('task/add', {text: 'brand new task', project: 'Test'});
    }""")

    # The api() call already re-renders; wait for DOM update
    expect(page.locator("#next-list")).to_contain_text("brand new task")


# ---------------------------------------------------------------------------
# 5. test_done_task_strikethrough
#    In the done search view, completed project tasks get strikethrough via
#    .done-project-task-completed > span. Active tasks should never have it.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_done_task_strikethrough(page, server_url, viewport):
    seed(
        active=[Task(text="still active", project="MyProj")],
        done=[Task(text="completed task", project="MyProj", done=True)],
        projects=[ProjectInfo(name="MyProj")],
    )
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    # Active task should NOT have line-through
    active_text = page.locator("#active-list .task-text").first
    expect(active_text).to_be_visible()
    active_decoration = active_text.evaluate("el => getComputedStyle(el).textDecoration")
    assert "line-through" not in active_decoration

    # Search for the project in done section to trigger search view
    # where completed tasks get strikethrough
    search_input = page.locator("#done-search-input")
    search_input.fill("MyProj")
    page.wait_for_timeout(300)

    # The completed task in search results should have strikethrough
    completed_el = page.locator(".done-project-task-completed span").first
    expect(completed_el).to_be_visible()
    done_decoration = completed_el.evaluate("el => getComputedStyle(el).textDecoration")
    assert "line-through" in done_decoration


# ---------------------------------------------------------------------------
# 6. test_mobile_voice_fab_visible
# ---------------------------------------------------------------------------

def test_mobile_voice_fab_visible(page, server_url):
    seed()
    page.set_viewport_size(IPHONE_VIEWPORT)
    _navigate(page, server_url)

    fab = page.locator("#voice-fab")
    expect(fab).to_be_visible()


# ---------------------------------------------------------------------------
# 7. test_desktop_voice_fab_hidden
# ---------------------------------------------------------------------------

def test_desktop_voice_fab_hidden(page, server_url):
    seed()
    page.set_viewport_size(DESKTOP_VIEWPORT)
    _navigate(page, server_url)

    fab = page.locator("#voice-fab")
    expect(fab).to_be_hidden()


# ---------------------------------------------------------------------------
# 8. test_mobile_chat_fab_visible
# ---------------------------------------------------------------------------

def test_mobile_chat_fab_visible(page, server_url):
    seed()
    page.set_viewport_size(IPHONE_VIEWPORT)
    _navigate(page, server_url)

    fab = page.locator("#fab-add")
    expect(fab).to_be_visible()


# ---------------------------------------------------------------------------
# 9. test_desktop_chat_fab_hidden
# ---------------------------------------------------------------------------

def test_desktop_chat_fab_hidden(page, server_url):
    seed()
    page.set_viewport_size(DESKTOP_VIEWPORT)
    _navigate(page, server_url)

    fab = page.locator("#fab-add")
    expect(fab).to_be_hidden()


# ---------------------------------------------------------------------------
# 10. test_done_search
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_done_search(page, server_url, viewport):
    seed(
        active=[],
        up_next=[],
        done=[
            Task(text="fix login bug", project="Auth", done=True),
            Task(text="add dark mode", project="UI", done=True),
            Task(text="write docs", project="Docs", done=True),
        ],
        projects=[ProjectInfo(name="Auth"), ProjectInfo(name="UI"), ProjectInfo(name="Docs")],
    )
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    search_input = page.locator("#done-search-input")
    done_list = page.locator("#done-list")

    # All 3 done tasks visible initially (in recent list)
    expect(done_list).to_contain_text("fix login bug")
    expect(done_list).to_contain_text("add dark mode")
    expect(done_list).to_contain_text("write docs")

    # Type a project name to filter via search view
    search_input.fill("Auth")
    page.wait_for_timeout(300)

    # Only matching project/task should be visible
    expect(done_list).to_contain_text("fix login bug")
    expect(done_list).not_to_contain_text("add dark mode")
    expect(done_list).not_to_contain_text("write docs")


# ---------------------------------------------------------------------------
# 11. test_project_section_renders
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_project_section_renders(page, server_url, viewport):
    seed(
        active=[],
        up_next=[],
        projects=[
            ProjectInfo(name="Alpha", description="first project"),
            ProjectInfo(name="Beta", description="second project"),
        ],
    )
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    project_list = page.locator("#project-list")
    expect(project_list).to_contain_text("Alpha")
    expect(project_list).to_contain_text("Beta")


# ---------------------------------------------------------------------------
# 12. test_mobile_chat_panel_fullwidth
# ---------------------------------------------------------------------------

def test_mobile_chat_panel_fullwidth(page, server_url):
    seed()
    page.set_viewport_size(IPHONE_VIEWPORT)
    _navigate(page, server_url)

    chat_panel = page.locator("#chat-panel")
    # On mobile, the chat panel should have width: 100vw = 375px
    width = chat_panel.evaluate("el => getComputedStyle(el).width")
    assert width == "375px"


# ---------------------------------------------------------------------------
# Shared seed data for UX tests
# ---------------------------------------------------------------------------

def _seed_rich_data():
    """Seed with enough data to make sizing/uniformity tests meaningful."""
    seed(
        active=[
            Task(text="implement user auth flow", project="Alpha"),
            Task(text="fix database migration", project="Alpha"),
            Task(text="design landing page", project="Beta"),
            Task(text="write API documentation", project="Beta"),
        ],
        up_next=[
            Task(text="set up CI pipeline", project="Alpha"),
            Task(text="add error monitoring", project="Beta"),
            Task(text="refactor data layer", project="Gamma"),
        ],
        done=[
            Task(text="initial project setup", project="Alpha", done=True),
            Task(text="deploy staging env", project="Beta", done=True),
            Task(text="create wireframes", project="Gamma", done=True),
        ],
        projects=[
            ProjectInfo(name="Alpha", description="main product"),
            ProjectInfo(name="Beta", description="marketing site"),
            ProjectInfo(name="Gamma", description="internal tools"),
        ],
    )


# ---------------------------------------------------------------------------
# 13. test_no_horizontal_scroll
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_no_horizontal_scroll(page, server_url, viewport):
    _seed_rich_data()
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    issues = check_no_horizontal_scroll(page)
    assert not issues, f"Horizontal scroll issues: {issues}"


# ---------------------------------------------------------------------------
# 14. test_touch_targets_mobile
# ---------------------------------------------------------------------------

def test_touch_targets_mobile(page, server_url):
    _seed_rich_data()
    page.set_viewport_size(IPHONE_VIEWPORT)
    _navigate(page, server_url)

    issues = check_touch_targets(page)
    assert not issues, f"Touch target issues on mobile: {issues}"


# ---------------------------------------------------------------------------
# 15. test_font_readability
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_font_readability(page, server_url, viewport):
    _seed_rich_data()
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    issues = check_font_readability(page)
    # Exclude decorative arrow icons (visual indicators, not readable text)
    issues = [i for i in issues if ".section-arrow" not in i and ".project-arrow" not in i]
    assert not issues, f"Font readability issues: {issues}"


# ---------------------------------------------------------------------------
# 16. test_button_uniformity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_button_uniformity(page, server_url, viewport):
    _seed_rich_data()
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    issues = check_button_uniformity(page)
    assert not issues, f"Button uniformity issues: {issues}"


# ---------------------------------------------------------------------------
# 17. test_task_list_uniform_sizing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_task_list_uniform_sizing(page, server_url, viewport):
    _seed_rich_data()
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    issues = []
    # Check active list tasks have uniform height
    issues.extend(check_uniform_sibling_sizing(page, "#active-list", ".task-item"))
    # Check next list tasks have uniform height
    issues.extend(check_uniform_sibling_sizing(page, "#next-list", ".task-item"))
    assert not issues, f"Task list sizing issues: {issues}"


# ---------------------------------------------------------------------------
# 18. test_section_headers_uniform
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_section_headers_uniform(page, server_url, viewport):
    _seed_rich_data()
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    # All section headers should have the same height
    issues = page.evaluate("""() => {
        const issues = [];
        const headers = document.querySelectorAll('.section-header, .collapsible-header');
        if (headers.length < 2) return issues;
        const heights = Array.from(headers).map(h => {
            const style = getComputedStyle(h);
            if (style.display === 'none' || style.visibility === 'hidden') return null;
            return h.getBoundingClientRect().height;
        }).filter(h => h !== null && h > 0);
        if (heights.length < 2) return issues;
        const maxH = Math.max(...heights), minH = Math.min(...heights);
        if (maxH - minH > 4) {
            issues.push(`Section headers height varies: ${minH.toFixed(1)}-${maxH.toFixed(1)}px across ${heights.length} headers`);
        }
        return issues;
    }""")
    assert not issues, f"Section header uniformity issues: {issues}"


# ---------------------------------------------------------------------------
# 19. test_key_elements_in_viewport
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_key_elements_in_viewport(page, server_url, viewport):
    _seed_rich_data()
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    # Only check above-the-fold sections -- done-section is naturally below fold
    key_selectors = [
        "#active-section",
        "#next-section",
    ]
    issues = check_elements_in_viewport(page, key_selectors)
    assert not issues, f"Elements outside viewport: {issues}"
    # done-section should exist even if below fold
    assert page.locator("#done-section").count() == 1


# ---------------------------------------------------------------------------
# 20. test_clickable_not_obscured
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_clickable_not_obscured(page, server_url, viewport):
    _seed_rich_data()
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    issues = check_clickable_not_obscured(page)
    # FABs are floating overlays by design -- they may cover bottom-right elements
    # but those elements are still accessible by scrolling
    issues = [i for i in issues if "voice-fab" not in i and "fab-add" not in i]
    assert not issues, f"Obscured clickable elements: {issues}"


# ---------------------------------------------------------------------------
# 21. test_project_cards_uniform
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_project_cards_uniform(page, server_url, viewport):
    _seed_rich_data()
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    issues = check_uniform_sibling_sizing(page, "#project-list", ".project-card", tolerance_px=4)
    assert not issues, f"Project card sizing issues: {issues}"


# ---------------------------------------------------------------------------
# 22. test_no_text_overflow
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("viewport", [DESKTOP_VIEWPORT, IPHONE_VIEWPORT], ids=["desktop", "mobile"])
def test_no_text_overflow(page, server_url, viewport):
    _seed_rich_data()
    page.set_viewport_size(viewport)
    _navigate(page, server_url)

    issues = check_no_text_overflow(page)
    assert not issues, f"Text overflow issues: {issues}"
