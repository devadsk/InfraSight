import json
from pathlib import Path

def generate_markdown_table(results_path: Path) -> str:
    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    lines = []
    lines.append("| Scenario | Description | Category | Expected Status | Actual Status | Strict | Adj | Device | Evidence | Policy | Cost ($) |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    for r in results:
        sid = r.get("scenario_id", "")
        name = r.get("name", "")
        st_exp = r.get("expected_status", "")
        st_act = r.get("actual_status", "")
        strict = "PASS" if r.get("status_correct") else "**FAIL**"
        adj = "PASS" if r.get("adjusted_status_correct") else "**FAIL**"
        dev = "OK" if r.get("device_correct") else "**FAIL**"
        ev = r.get("evidence_correct")
        ev_str = "N/A" if ev == "N/A" else ("OK" if ev else "**FAIL**")
        pol = "OK" if r.get("policy_correct") else "**FAIL**"
        cost = f"${r.get('estimated_cost_usd', 0.0):.4f}"

        # Category mapping
        cat = "Development"
        if sid in ("SCN-14", "SCN-15", "SCN-17"):
            cat = "Same-Logic Variant"
        elif sid == "SCN-16":
            cat = "Development (Uncataloged)"

        lines.append(f"| **{sid}** | {name} | {cat} | `{st_exp}` | `{st_act}` | {strict} | {adj} | {dev} | {ev_str} | {pol} | {cost} |")

    return "\n".join(lines)

def main():
    p = Path("eval/results.json")
    if not p.exists():
        p = Path("eval/results_baseline.json")
    table = generate_markdown_table(p)
    print(table)

if __name__ == "__main__":
    main()

