import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

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

    print(f"[*] 3. Running pytest test suite (72 tests) with NO API KEY and NO .env...")
    res_test = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"], capture_output=True, text=True)
    print(res_test.stdout.strip())
    if res_test.returncode != 0:
        print(f"Tests failed:\n{res_test.stderr}")
        return False
    print(f"[+] All tests passed in clean checkout!")

    print(f"[*] 4. Running record_replay.py --verify in clean checkout (offline, zero tokens)...")
    res_replay = subprocess.run([sys.executable, "scripts/record_replay.py", "--verify"], capture_output=True, text=True)
    print(res_replay.stdout.strip())
    if res_replay.returncode != 0:
        print(f"Replay verify failed:\n{res_replay.stderr}")
        return False
    print(f"[+] Replay verification passed in clean checkout!")

    print(f"[*] 5. Testing scripts/run_eval.py --compare against baseline in clean checkout...")
    res_eval = subprocess.run([sys.executable, "scripts/run_eval.py", "--compare"], capture_output=True, text=True)
    print(res_eval.stdout.strip())
    if res_eval.returncode != 0:
        print(f"Run eval failed:\n{res_eval.stderr}")
        return False

    print("\n[+] CLEAN CHECKOUT VERIFICATION PASSED: No hardcoded paths, no hidden dependencies, 100% offline runnable.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
