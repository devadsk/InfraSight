"""
Automated Screenshot Capture for InfraSight (Phase 5).
Uses Playwright to capture high-resolution UI screenshots of hero scenarios,
approval gates, safety denials, model activity ledger, and post-incident reports.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = Path("docs/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_PORT = 8000
FRONTEND_PORT = 8501


def wait_for_port(port: int, timeout: float = 20.0):
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.5)
    return False


def kill_ports():
    import socket
    for port in [BACKEND_PORT, FRONTEND_PORT]:
        cmd = f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"
        subprocess.run(["powershell", "-Command", cmd], capture_output=True)
    time.sleep(1)


def main():
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    print("[*] Cleaning ports and starting backend and frontend processes...")
    kill_ports()
    backend_proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "backend.main:app",
        "--host", "127.0.0.1", "--port", str(BACKEND_PORT), "--log-level", "warning"
    ])
    frontend_proc = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "frontend/app.py",
        "--server.port", str(FRONTEND_PORT), "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    ])

    try:
        print("[*] Waiting for services to become ready...")
        if not wait_for_port(BACKEND_PORT, 20.0):
            raise RuntimeError(f"Backend failed to start on port {BACKEND_PORT}")
        if not wait_for_port(FRONTEND_PORT, 25.0):
            raise RuntimeError(f"Frontend failed to start on port {FRONTEND_PORT}")
        print("[*] Services ready! Launching Playwright browser...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 950})

            # -------------------------------------------------------------
            # Screenshot 1: Hero 2 - Rebuild Contradiction (Amber != Failed)
            # -------------------------------------------------------------
            print("[*] Loading Streamlit UI...")
            page.goto(f"http://127.0.0.1:{FRONTEND_PORT}", wait_until="networkidle")
            page.wait_for_timeout(3000)

            # Check if an old investigation is loaded and clear it
            clear_sel = page.locator("button:has-text('Clear / New Investigation')")
            if clear_sel.count() > 0:
                clear_sel.first.click()
                page.wait_for_timeout(2000)

            # Wait for Start Investigation button and click it
            print("[*] Running Hero 2 (SCN-02 Rebuild Contradiction)...")
            start_btn = page.wait_for_selector("button:has-text('Start Investigation')", timeout=15000)
            start_btn.click()
            print("[*] Clicked Start Investigation. Waiting for diagnosis...")

            # Wait for diagnosis card to render
            try:
                page.wait_for_selector("text=NOT_CONFIRMED", timeout=30000)
                page.wait_for_timeout(2000)
            except Exception as e:
                debug_shot = SCREENSHOT_DIR / "debug_page.png"
                page.screenshot(path=str(debug_shot), full_page=True)
                print(f"[!] Saved debug screenshot to {debug_shot}")
                page_text = page.inner_text("body")
                with open("docs/screenshots/debug_text.txt", "w", encoding="utf-8") as f:
                    f.write(page_text)
                raise e

            shot1 = SCREENSHOT_DIR / "01_hero2_rebuild_contradiction.png"
            page.screenshot(path=str(shot1), full_page=False)
            print(f"[+] Saved: {shot1}")

            # -------------------------------------------------------------
            # Screenshot 2: Multimodal Image & Pixel Perception Tab
            # -------------------------------------------------------------
            print("[*] Capturing Multimodal Image & Perception Tab...")
            page.locator("text=Image & Perception").first.click()
            page.wait_for_timeout(2000)
            shot2 = SCREENSHOT_DIR / "02_multimodal_perception_tab.png"
            page.screenshot(path=str(shot2), full_page=False)
            print(f"[+] Saved: {shot2}")

            # -------------------------------------------------------------
            # Screenshot 3: Meta Model Activity Tab (Accounting Ledger)
            # -------------------------------------------------------------
            print("[*] Capturing Meta Model Activity Tab...")
            page.locator("text=Meta Model Activity").first.click()
            page.wait_for_timeout(2000)
            shot3 = SCREENSHOT_DIR / "03_meta_model_accounting_ledger.png"
            page.screenshot(path=str(shot3), full_page=False)
            print(f"[+] Saved: {shot3}")

            # -------------------------------------------------------------
            # Screenshot 4: Post-Incident Markdown Audit Report Tab
            # -------------------------------------------------------------
            print("[*] Capturing Post-Incident Audit Report Tab...")
            page.locator("text=Post-Incident Report").first.click()
            page.wait_for_timeout(2000)
            shot4 = SCREENSHOT_DIR / "04_markdown_incident_report.png"
            page.screenshot(path=str(shot4), full_page=False)
            print(f"[+] Saved: {shot4}")

            # -------------------------------------------------------------
            # Screenshot 5: Policy Stress Test (Scripted Adversarial Model - Safety Moment)
            # -------------------------------------------------------------
            print("[*] Running Policy Stress Test (Scripted Adversarial Model)...")
            # Clear / Reset
            clear_sel = page.locator("button:has-text('Clear / New Investigation')")
            if clear_sel.count() > 0:
                clear_sel.first.click()
                page.wait_for_timeout(2000)

            # Click Policy Stress Test button
            stress_btn = page.wait_for_selector("button:has-text('Policy Stress Test')", timeout=10000)
            stress_btn.click()
            print("[*] Clicked Policy Stress Test button. Waiting for safety enforcement panel...")

            try:
                page.wait_for_selector("text=Security & Safety Policy Enforcements", timeout=30000)
                page.wait_for_selector("text=Scripted adversarial requests", timeout=30000)
                page.wait_for_timeout(2000)
            except Exception as e:
                debug_shot = SCREENSHOT_DIR / "debug_page_stress.png"
                page.screenshot(path=str(debug_shot), full_page=True)
                page_text = page.inner_text("body")
                with open("docs/screenshots/debug_text_stress.txt", "w", encoding="utf-8") as f:
                    f.write(page_text)
                raise e

            shot5 = SCREENSHOT_DIR / "05_class_c_safety_denial.png"
            page.screenshot(path=str(shot5), full_page=False)
            print(f"[+] Saved: {shot5}")

            # Remove temporary debug files if all succeed
            for dbg in ["debug_info.txt", "debug_page.png", "debug_text.txt", "debug_page_scn10.png", "debug_text_scn10.txt", "debug_page_stress.png", "debug_text_stress.txt"]:
                dbg_p = SCREENSHOT_DIR / dbg
                if dbg_p.exists():
                    dbg_p.unlink()

            browser.close()
            print("\n[+] All 5 UI screenshots successfully captured into docs/screenshots/!")

    finally:
        print("[*] Stopping background servers...")
        try:
            frontend_proc.terminate()
            backend_proc.terminate()
            frontend_proc.wait(timeout=3)
            backend_proc.wait(timeout=3)
        except Exception:
            frontend_proc.kill()
            backend_proc.kill()


if __name__ == "__main__":
    main()
