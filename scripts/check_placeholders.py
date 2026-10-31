import re
import sys
from pathlib import Path

def check_submission_placeholders(path: Path = Path("docs/SUBMISSION.md")) -> bool:
    if not path.exists():
        print(f"Error: {path} not found.")
        return False

    content = path.read_text(encoding="utf-8")
    errors = []

    # Check for unauthorized placeholders (only {{TO_FILL_BY_DEVELOPER: ...}} is permitted for human completion)
    matches = re.findall(r"\{\{.*?\}\}", content)
    unauthorized = [m for m in matches if not m.startswith("{{TO_FILL_BY_DEVELOPER:")]
    if unauthorized:
        errors.append(f"Found {len(unauthorized)} unauthorized placeholder markers: {unauthorized}")

    # Check for forbidden example placeholder domains/urls
    ex_lines = [l.strip() for l in content.splitlines() if "example.com" in l.lower() or "http://example" in l.lower()]
    if ex_lines:
        errors.append(f"Found forbidden 'example' placeholder occurrences: {ex_lines}")

    # Check for localhost URLs
    lh_lines = [l.strip() for l in content.splitlines() if "localhost" in l.lower()]
    if lh_lines:
        errors.append(f"Found forbidden 'localhost' URL occurrences: {lh_lines}")

    if errors:
        print("[FAIL] Placeholder validation failed in docs/SUBMISSION.md:")
        for err in errors:
            print(f"  - {err}")
        return False
    else:
        print(f"[PASS] docs/SUBMISSION.md verified: {len(matches)} developer placeholders ready for submission, 0 unauthorized placeholders, 0 example URLs, 0 localhost URLs.")
        return True

if __name__ == "__main__":
    success = check_submission_placeholders()
    sys.exit(0 if success else 1)

