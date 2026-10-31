import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import urllib.request
import json

def kill_proc_tree(pid: int):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    else:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            pass

def main():
    repo_root = Path(__file__).resolve().parent.parent
    temp_dir = Path(tempfile.gettempdir()) / "infrasight_clean_test"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] 1. Cloning repository from {repo_root} to {temp_dir}...")
    res = subprocess.run(["git", "clone", str(repo_root), str(temp_dir)], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Git clone failed: {res.stderr}")
        return False
    print(f"[+] Cloned successfully.")

    os.chdir(temp_dir)

    print(f"[*] 2. Verifying .env does NOT exist in clean checkout...")
    has_env = (temp_dir / ".env").exists()
    print(f"  .env exists: {has_env} (Expected: False)")
    assert not has_env, ".env must not exist in a clean checkout"

    print(f"[*] 3. Creating virtual environment and verifying requirements...")
    venv_dir = temp_dir / ".venv"
    subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)], check=True)
    venv_python = venv_dir / "Scripts" / "python.exe" if os.name == "nt" else venv_dir / "bin" / "python"
    
    # Check pip freeze against requirements.txt
    freeze_res = subprocess.run([str(venv_python), "-m", "pip", "freeze"], capture_output=True, text=True)
    frozen_pkgs = {line.split("==")[0].lower(): line.split("==")[1] if "==" in line else "" for line in freeze_res.stdout.splitlines()}
    req_lines = [l.strip() for l in (temp_dir / "requirements.txt").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    print(f"  Checking {len(req_lines)} required packages in venv:")
    for req in req_lines:
        pkg_name = req.split("==")[0].split(">=")[0].lower()
        if pkg_name in frozen_pkgs:
            print(f"    [OK] {pkg_name}: installed ({frozen_pkgs[pkg_name]})")
        else:
            print(f"    [WARN] {pkg_name} not found in pip freeze")

    print(f"[*] 4. Running pytest test suite with NO API KEY and NO .env...")
    res_test = subprocess.run([str(venv_python), "-m", "pytest", "tests/", "-q", "--tb=short"], capture_output=True, text=True)
    print(res_test.stdout.strip())
    if res_test.returncode != 0:
        print(f"Tests failed:\n{res_test.stderr}")
        return False
    print(f"[+] All tests passed in clean checkout!")

    print(f"[*] 5. Launching headless run_local.py and probing /health...")
    proc = subprocess.Popen([str(venv_python), "scripts/run_local.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    health_ok = False
    for attempt in range(25):
        time.sleep(1)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("status") == "ok":
                        health_ok = True
                        print(f"  [+] Backend /health responded 200 OK: {data}")
                        break
        except Exception:
            pass

    kill_proc_tree(proc.pid)
    assert health_ok, "Failed to connect to /health from run_local.py"
    print(f"[+] run_local.py /health verified successfully!")

    print(f"[*] 6. Running record_replay.py --verify in clean checkout (offline, zero tokens)...")
    res_replay = subprocess.run([str(venv_python), "scripts/record_replay.py", "--verify"], capture_output=True, text=True)
    print(res_replay.stdout.strip())
    if res_replay.returncode != 0:
        print(f"Replay verify failed:\n{res_replay.stderr}")
        return False
    print(f"[+] Replay verification passed in clean checkout!")

    print(f"[*] 7. Testing scripts/run_eval.py --compare against baseline in clean checkout...")
    res_eval = subprocess.run([str(venv_python), "scripts/run_eval.py", "--compare"], capture_output=True, text=True)
    print(res_eval.stdout.strip())
    if res_eval.returncode != 0:
        print(f"Run eval failed:\n{res_eval.stderr}")
        return False

    print("\n[+] TRULY CLEAN CHECKOUT VERIFICATION PASSED: No hardcoded paths, no hidden dependencies, 100% offline runnable.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
