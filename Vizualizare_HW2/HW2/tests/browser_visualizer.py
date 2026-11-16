"""Optional real-browser checks; no web server is needed.

uv run --with playwright python tests/browser_visualizer.py
Uses an existing Google Chrome installation by default; override CHROME_PATH.
"""
import json
import os
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as p, tempfile.TemporaryDirectory(prefix="matrix-lab-") as temporary:
        browser = p.chromium.launch(
            executable_path=os.environ.get("CHROME_PATH", "/usr/bin/google-chrome"),
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, color_scheme="light")
        errors = []
        page.on("pageerror", lambda exception: errors.append(str(exception)))
        page.goto((ROOT / "interactive.html").as_uri())
        snapshot = lambda: page.evaluate("MatrixLabUI.snapshot()")
        show = lambda name: page.locator("#tab-" + name).click()
        show("execution")
        # Supplemental controls start collapsed, while the main homework settings stay visible.
        expect(page.locator("#other-settings")).not_to_have_attribute("open", "")
        for control in ("max-levels", "dispatch-seed", "arithmetic", "b-layout", "unsafe"):
            expect(page.locator("#" + control)).to_be_hidden()
        for control in ("strategy", "thread-mode", "schedule-all"):
            expect(page.locator("#" + control)).to_be_visible()
        page.locator("#other-settings > summary").click()
        for control in ("schedule-all", "max-levels", "dispatch-seed", "arithmetic", "b-layout", "unsafe"):
            expect(page.locator("#" + control)).to_be_visible()
        expect(page.locator("#dispatch-seed")).to_be_visible()
        expect(page.locator("#error")).to_be_hidden()
        assert page.locator("#strategy option").count() == 13
        strategies = page.locator("#strategy option").evaluate_all("options => options.map(o => o.value)")
        for strategy in strategies:
            page.locator("#strategy").select_option(strategy)
            source_name = "sequential" if strategy == "seq" else strategy
            expect(page.locator("#kernel-source-title")).to_have_text(source_name + "(p)")
            assert page.locator("#kernel-source .source-text").count() > 4
            assert page.locator("#live-code-panel .code-line.running").count() > 0
            assert page.locator("#trace-scopes .trace-scope").count() == 3
            uses_dot = strategy in ("seq", "parallel_i", "parallel_j", "collapse_ij", "nested_ij")
            assert page.locator("#dot-source-panel").is_visible() == uses_dot
            for index in "ijk":
                expect(page.locator(f'#trace-indexes [data-index="{index}"] .index-value')).to_have_text(
                    str(snapshot()["trace"][index]))
            page.locator("#last").click()
            expect(page.locator("#result-status")).to_have_text("All result cells match the reference")
            expect(page.locator("#trace-status")).to_contain_text("Finished")
            assert page.locator("#live-code-panel .code-line.running").count() == 0
            assert snapshot()["wave"] == snapshot()["duration"]

        # The helper's actual k loop and its value advance with execution.
        page.locator("#reset").click()
        for k in range(4):
            assert snapshot()["trace"]["k"] == k
            expect(page.locator("#slice-label")).to_have_text(str(k))
            expect(page.locator('#dot-source [data-loop="k"] .line-note')).to_contain_text(f"k = {k}")
            assert page.locator('#dot-source [data-operation="true"].running').count() == 1
            if k < 3:
                page.locator("#next").click()
        page.locator("#next").click()
        assert snapshot()["trace"]["j"] == 1 and snapshot()["trace"]["k"] == 0
        page.locator("#first").click()
        page.locator("#play").click()
        page.wait_for_function("MatrixLabUI.snapshot().wave >= 2")
        if page.locator("#play").inner_text() == "Pause":
            page.locator("#play").click()
        assert snapshot()["trace"]["k"] == snapshot()["wave"] % snapshot()["config"]["m"]
        expect(page.locator("#slice-label")).to_have_text(str(snapshot()["trace"]["k"]))

        # Several threads can have different k values on the very same C line.
        page.locator("#strategy").select_option("parallel_k")
        active = page.locator("#trace-active-workers .trace-thread")
        assert active.count() == 4
        assert len(set(active.locator("code").all_text_contents())) == 4
        active.nth(1).click()
        assert snapshot()["trace"]["worker"] == "2" and snapshot()["trace"]["k"] == 1
        expect(page.locator("#trace-worker")).to_have_value("2")
        expect(page.locator("#slice-label")).to_have_text("1")

        # A future cell is an inspection, not a falsely highlighted active operation.
        page.locator("#strategy").select_option("seq")
        show("matrices")
        page.locator("#matrix-c button").last.click()
        show("execution")
        assert snapshot()["trace"]["phase"] == "upcoming"
        expect(page.locator("#trace-follow")).to_have_value("cell")
        assert page.locator("#live-code-panel .code-line.running").count() == 0
        assert page.locator("#live-code-panel .code-line.inspecting").count() > 0
        show("cell")
        page.locator("#slice").fill("2")
        page.locator("#slice").dispatch_event("input")
        assert snapshot()["trace"]["k"] == 2 and snapshot()["trace"]["pinned"]
        show("execution")
        page.locator("#trace-follow").select_option("execution")
        assert snapshot()["trace"]["phase"] == "active"
        page.locator("#trace-matrix button").last.click()
        expect(page.locator("#trace-follow")).to_have_value("cell")

        page.locator("#strategy").select_option("nested_ijk")
        page.locator("#budget").fill("8")
        page.locator("#budget").press("Tab")
        expect(page.locator("#team-chips")).to_contain_text("i: 2")
        page.locator("#thread-mode").select_option("explicit")
        for loop, count in zip("ijk", (2, 3, 2)):
            page.locator(f"#threads-{loop}").fill(str(count))
            page.locator(f"#threads-{loop}").press("Tab")
        for loop, policy in zip("ijk", ("dynamic", "guided", "static")):
            page.locator(f"#schedule-{loop}").select_option(policy)
        expect(page.locator("#schedule-all")).to_have_value("mixed")
        page.locator("#max-levels").select_option("1")
        expect(page.locator("#team-list")).to_contain_text("serialized")
        expect(page.locator('#kernel-source [data-loop="k"] .line-note')).to_contain_text("serialized")
        page.locator("#max-levels").select_option("3")
        page.locator("#last").click()
        expect(page.locator("#result-status")).to_contain_text("match")

        # Editing, selection, k slices, thread focus and both memory layouts.
        show("matrices")
        page.locator("#matrix-a input").first.fill("7")
        page.locator("#matrix-a input").first.press("Tab")
        assert snapshot()["config"]["a"][0][0] == "7"
        expect(page.locator("#preset")).to_have_value("custom")
        page.locator("#matrix-c button").nth(4).click()
        assert snapshot()["selected"] == {"i": 1, "j": 1, "k": 0}
        show("cell")
        page.locator("#slice").fill("2")
        page.locator("#slice").dispatch_event("input")
        assert snapshot()["selected"]["k"] == 2
        worker = snapshot()["workers"][-1]
        show("threads")
        page.locator("#worker-focus").select_option(worker)
        expect(page.locator("#matrix-c .faded")).not_to_have_count(0)
        page.locator("#worker-focus").select_option("")
        previous_truth = snapshot()["truth"]
        page.locator("#b-layout").select_option("transposed")
        assert snapshot()["truth"] == previous_truth
        page.locator("#arithmetic").select_option("exact")

        # Paste a small known example and deliberately lose concurrent writes.
        show("matrices")
        page.locator("summary").filter(has_text="Paste matrices").click()
        page.locator("#paste-a").fill("1 2 3 4")
        page.locator("#paste-b").fill("1\n1\n1\n1")
        page.locator("#apply-paste").click()
        page.locator("#strategy").select_option("parallel_k")
        page.locator("#thread-mode").select_option("budget")
        page.locator("#budget").fill("4")
        page.locator("#budget").press("Tab")
        page.locator("#schedule-all").select_option("static")
        page.locator("#chunk-k").fill("0")
        page.locator("#chunk-k").press("Tab")
        assert snapshot()["truth"] == [["10"]]
        page.locator("#unsafe").check()
        show("execution")
        expect(page.locator("#trace-unsafe-panel")).to_be_visible()
        assert page.locator("#unsafe-source .running").count() == 1
        assert page.locator("#kernel-source .running").count() == 0
        expect(page.locator("#trace-qualification")).to_contain_text("safe source")
        page.locator("#last").click()
        expect(page.locator("#result-status")).to_contain_text("wrong cell")
        expect(page.locator("#matrix-c .value")).not_to_have_text("10")
        page.locator("#unsafe").uncheck()
        page.locator("#last").click()
        expect(page.locator("#matrix-c .value")).to_have_text("10")

        # Play, pause and slider scrubbing keep the controls consistent.
        page.locator("#first").click()
        page.locator("#play").click()
        expect(page.locator("#play")).to_have_text("Pause")
        page.wait_for_function("MatrixLabUI.snapshot().wave > 0")
        if page.locator("#play").inner_text() == "Pause":
            page.locator("#play").click()
        page.locator("#wave").fill("0")
        page.locator("#wave").dispatch_event("input")
        assert snapshot()["wave"] == 0

        show("matrices")
        # JSON save/load round-trips actual matrix entries and all options.
        with page.expect_download() as download_info:
            page.locator("#save-config").click()
        setup = Path(temporary) / "setup.json"
        download_info.value.save_as(setup)
        saved = json.loads(setup.read_text())
        page.locator("#reset").click()
        page.locator("#config-file").set_input_files(setup)
        page.wait_for_function("MatrixLabUI.snapshot().config.n === 1")
        assert snapshot()["config"]["a"] == saved["a"]
        page.locator("#dim-n").fill("13")
        page.locator("#dim-n").press("Tab")
        expect(page.locator("#error")).to_be_visible()
        assert snapshot()["config"]["n"] == 1
        page.locator("#reset").click()

        # Large exact arithmetic stays exact and does not overflow code/inspector panels.
        page.locator("#arithmetic").select_option("exact")
        huge = "1" + "0" * 80
        page.locator("#matrix-a input").first.fill(huge)
        page.locator("#matrix-a input").first.press("Tab")
        page.locator("#matrix-b input").first.fill(huge)
        page.locator("#matrix-b input").first.press("Tab")
        assert len(snapshot()["truth"][0][0]) >= 160
        for width in (1440, 728, 390, 320):
            page.set_viewport_size({"width": width, "height": 1100})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, "large integers")
        page.set_viewport_size({"width": 1440, "height": 1100})
        page.locator("#reset").click()

        # Responsive layouts and both themes stay within the page width.
        for width in (1440, 728, 390, 320):
            for scheme in ("light", "dark"):
                page.set_viewport_size({"width": width, "height": 1100})
                page.emulate_media(color_scheme=scheme)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, scheme)
                if width <= 850:
                    expect(page.locator("#toggle-settings")).to_be_visible()
                    if page.locator("#toggle-settings").get_attribute("aria-expanded") == "false":
                        page.locator("#toggle-settings").click()
                    expect(page.locator("#budget")).to_be_visible()
                    page.locator("#close-settings").click()
                if width in (1440, 390):
                    page.screenshot(path=f"/tmp/matrix-lab-{width}-{scheme}.png", full_page=True)
        # Tabs replace the old vertical document; playback and setup survive navigation.
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator("#reset").click()
        show("matrices")
        for key in "nmr":
            page.locator("#dim-" + key).fill("10")
            page.locator("#dim-" + key).press("Tab")
        page.locator("#strategy").select_option("collapse_jk")
        page.locator("#next").click()
        current_wave = snapshot()["wave"]
        for name in ("execution", "cell", "threads", "matrices"):
            show(name)
            assert snapshot()["tab"] == name and snapshot()["wave"] == current_wave
            assert page.locator('[role="tabpanel"]:visible').count() == 1
            expect(page.locator("#play")).to_be_in_viewport()
            expect(page.locator("#wave")).to_be_in_viewport()
            expect(page.locator("#strategy")).to_be_in_viewport()
            assert page.evaluate("document.documentElement.scrollHeight <= innerHeight")
            assert page.evaluate("document.querySelector('.sidebar').getBoundingClientRect().right <= document.querySelector('.workspace').getBoundingClientRect().left")
        # Normal sized matrices fit without scrolling the active panel.
        paste_details = page.locator("details").filter(has=page.locator("#paste-a"))
        if paste_details.get_attribute("open") is not None:
            paste_details.locator("summary").click()
        page.wait_for_timeout(100)
        assert page.locator("#panel-matrices").evaluate("p => p.scrollHeight <= p.clientHeight"), page.locator("#panel-matrices").evaluate("p => ({height:p.clientHeight,scroll:p.scrollHeight,cell:getComputedStyle(p.querySelector('.cell')).height,rows:MatrixLabUI.snapshot().config.n,pasteOpen:p.querySelector('details').open})")
        show("cell")
        page.wait_for_timeout(100)
        assert page.locator("#panel-cell").evaluate("p => p.scrollHeight <= p.clientHeight"), "10x10 cell panel should fit"
        # Keyboard tab navigation includes Home/End and keeps tab/panel selection in sync.
        page.locator("#tab-cell").focus()
        page.keyboard.press("ArrowLeft")
        assert snapshot()["tab"] == "execution"
        page.keyboard.press("End")
        assert snapshot()["tab"] == "threads"
        page.keyboard.press("Home")
        assert snapshot()["tab"] == "matrices"
        page.locator("#toggle-help").click()
        expect(page.locator("#strategy-description")).to_be_visible()
        page.locator("#toggle-help").click()
        expect(page.locator("#strategy-description")).to_be_hidden()
        page.locator("#fullscreen").click()
        page.wait_for_function("Boolean(document.fullscreenElement)")
        expect(page.locator("#fullscreen")).to_have_text("Exit full screen")
        page.locator("#fullscreen").click()
        page.wait_for_function("!document.fullscreenElement")
        for width, height in ((1440, 900), (1280, 720), (1024, 768), (728, 900), (390, 844), (320, 640)):
            page.set_viewport_size({"width": width, "height": height})
            for name in ("matrices", "execution", "cell", "threads"):
                show(name)
                page.wait_for_timeout(60)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, height, name, "width")
                assert page.evaluate("document.documentElement.scrollHeight <= innerHeight"), (width, height, name, "height")
                expect(page.locator("#play")).to_be_in_viewport()
                expect(page.locator("#tab-" + name)).to_be_in_viewport()
                if name == "execution":
                    expect(page.locator("#kernel-source")).to_be_in_viewport()
                    expect(page.locator("#trace-indexes")).to_be_in_viewport()
                if width == 1440 or (width == 390 and name == "execution"):
                    page.screenshot(path=f"/tmp/matrix-tabs-{width}-{name}.png")
            if width <= 850:
                page.locator("#toggle-settings").click()
                expect(page.locator("#strategy")).to_be_in_viewport()
                page.keyboard.press("Escape")
                expect(page.locator("#settings-panel")).to_be_hidden()
        assert not errors, errors
        browser.close()
    print("Browser checks passed: 13 strategies, exact source panels, live i/j/k and automatic k slices, "
          "concurrent thread tracing, future-cell inspection, editors/paste, nested teams, per-loop schedules, "
          "race demo, playback, JSON round-trip, keyboard tabs, persistent timeline, left settings, full-screen toggle, "
          "and bounded 320–1440 px layouts in light/dark themes.")


if __name__ == "__main__":
    main()
