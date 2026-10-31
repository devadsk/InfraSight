import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

def check_placeholders(allow_placeholders: bool = False) -> tuple[bool, list[dict]]:
    print("[1/5] Checking submission placeholders in docs/SUBMISSION.md and docs/DEMO_SCRIPT.md...")
    targets = [Path("docs/SUBMISSION.md"), Path("docs/DEMO_SCRIPT.md")]
    found_placeholders = []

    for path in targets:
        if not path.exists():
            print(f"  [FAIL] {path} missing")
            return False, []

        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            # Check for {{...}} markers
            matches = re.findall(r"(\{\{.*?\}\})", line)
            for m in matches:
                found_placeholders.append({
                    "file": str(path),
                    "line": idx,
                    "type": "placeholder",
                    "text": m
                })

            # Check for forbidden example/localhost URLs
            if "example.com" in line.lower() or "http://example" in line.lower():
                found_placeholders.append({
                    "file": str(path),
                    "line": idx,
                    "type": "forbidden_example_url",
                    "text": line.strip()
                })
            if "localhost" in line.lower():
                found_placeholders.append({
                    "file": str(path),
                    "line": idx,
                    "type": "forbidden_localhost_url",
                    "text": line.strip()
                })

    if found_placeholders:
        print(f"  Found {len(found_placeholders)} remaining placeholders/forbidden markers:")
        for p in found_placeholders:
            print(f"    - {p['file']}:{p['line']} [{p['type']}]: {p['text']}")

        if not allow_placeholders:
            print(f"  [FAIL] Release gate strictly prohibits placeholders (run with --allow-placeholders for dev only).")
            return False, found_placeholders
        else:
            print(f"  [WARN] Permitted {len(found_placeholders)} placeholders via --allow-placeholders flag.")
            return True, found_placeholders
    else:
        print("  [PASS] Zero placeholders, zero example domains, zero localhost URLs found.")
        return True, []


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
    parser = argparse.ArgumentParser(description="InfraSight Release & Final Submission Gate")
    parser.add_argument("--allow-placeholders", action="store_true",
                        help="Allow {{TO_FILL_BY_DEVELOPER}} placeholders during development testing")
    args = parser.parse_args()

    print("==================================================")
    print("  InfraSight Release & Final Submission Gate")
    print("==================================================")
    c1, placeholders = check_placeholders(allow_placeholders=args.allow_placeholders)
    c2 = check_fact_check_table()
    c3 = check_secrets_and_paths()
    c4 = check_unit_tests()
    c5 = check_replay_verification()

    print("\n" + "=" * 50)
    all_ok = c1 and c2 and c3 and c4 and c5
    if all_ok and len(placeholders) == 0:
        print("ALL RELEASE CHECKS PASSED: READY FOR SUBMISSION")
    elif all_ok and len(placeholders) > 0:
        print(f"RELEASE CHECKS PASSED (DEVELOPMENT RUN: {len(placeholders)} placeholders permitted)")
    elif len(placeholders) > 0 and not args.allow_placeholders:
        print(f"NOT READY: {len(placeholders)} placeholders remain")
    else:
        print("ONE OR MORE RELEASE CHECKS FAILED")
    print("=" * 50)
    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
