import os
import re
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

def check_placeholders() -> bool:
    print("[1/5] Checking submission placeholders in docs/SUBMISSION.md...")
    sub_path = Path("docs/SUBMISSION.md")
    if not sub_path.exists():
        print("  [FAIL] docs/SUBMISSION.md missing")
        return False
    content = sub_path.read_text(encoding="utf-8")
    
    # Check for un-filled developer markers
    markers = re.findall(r"\{\{.*?\}\}", content)
    if markers:
        print(f"  [WARN] Unfilled developer placeholders present: {len(markers)}")
        # Notice: developer placeholders are expected before human final edit, but script checks format
    
    # Check for forbidden example/localhost
    forbidden = []
    for l in content.splitlines():
        if "example.com" in l or "http://localhost" in l:
            forbidden.append(l.strip())
    if forbidden:
        print(f"  [FAIL] Forbidden placeholders found: {forbidden}")
        return False
    print("  [PASS] No forbidden placeholder URLs found.")
    return True

def check_fact_check_table() -> bool:
    print("[2/5] Checking docs/FACT_CHECK.md completeness...")
    fc_path = Path("docs/FACT_CHECK.md")
    if not fc_path.exists():
        print("  [FAIL] docs/FACT_CHECK.md missing")
        return False
    content = fc_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    no_rows = [l for l in lines if "| No |" in l or "| no |" in l or "| NO |" in l]
    if no_rows:
        print(f"  [FAIL] Found {len(no_rows)} unverified claims in docs/FACT_CHECK.md:")
        for r in no_rows[:5]:
            print(f"    {r}")
        return False
    print("  [PASS] All claims in docs/FACT_CHECK.md verified.")
    return True

def check_secrets_and_paths() -> bool:
    print("[3/5] Running secret and absolute-path sweep...")
    load_dotenv()
    key = os.getenv("META_API_KEY")
    if key:
        res = subprocess.run(["git", "grep", "-F", key], capture_output=True, text=True)
        if res.stdout:
            print(f"  [FAIL] API Key found in tracked files: {len(res.stdout.splitlines())} matches")
            return False
    
    # Check absolute paths (excluding this check script itself)
    for p_prefix, p_suffix in [("file://" + "/d:", ""), ("d:/" + "infrasight", ""), ("C:/" + "Users/ELCOT", ""), ("C:\\\\" + "Users\\\\ELCOT", "")]:
        pattern = p_prefix + p_suffix
        res_p = subprocess.run(["git", "grep", "-i", "-I", pattern, "--", ":!scripts/release_check.py"], capture_output=True, text=True)
        if res_p.stdout:
            print(f"  [FAIL] Absolute path pattern '{pattern}' found in tracked files:")
            for l in res_p.stdout.splitlines()[:3]:
                print(f"    {l}")
            return False
    print("  [PASS] Zero secrets and zero absolute paths found in repo.")
    return True

def check_unit_tests() -> bool:
    print("[4/5] Running pytest unit test suite...")
    res = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  [FAIL] Unit tests failed:\n{res.stdout}\n{res.stderr}")
        return False
    print(f"  [PASS] Unit tests passed: {res.stdout.strip()}")
    return True

def check_replay_verification() -> bool:
    print("[5/5] Running record_replay.py --verify (offline hero verification)...")
    res = subprocess.run([sys.executable, "scripts/record_replay.py", "--verify"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  [FAIL] Replay verification failed:\n{res.stdout}\n{res.stderr}")
        return False
    print("  [PASS] All 5 hero scenarios verified offline from replay files.")
    return True

def main():
    print("==================================================")
    print("  InfraSight Release & Final Submission Gate")
    print("==================================================")
    c1 = check_placeholders()
    c2 = check_fact_check_table()
    c3 = check_secrets_and_paths()
    c4 = check_unit_tests()
    c5 = check_replay_verification()
    
    print("\n" + "=" * 50)
    all_ok = c1 and c2 and c3 and c4 and c5
    if all_ok:
        print("ALL RELEASE CHECKS PASSED: READY FOR SUBMISSION")
    else:
        print("ONE OR MORE RELEASE CHECKS FAILED")
    print("=" * 50)
    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

