import sqlite3

conn = sqlite3.connect("data/infrasight.db")
c = conn.cursor()
c.execute("""
    SELECT SUBSTR(timestamp, 1, 10) as dt, model_id, purpose, is_replay, COUNT(*), SUM(total_tokens), SUM(estimated_cost_usd)
    FROM usage_ledger
    GROUP BY dt, model_id, purpose, is_replay
    ORDER BY dt, model_id, purpose, is_replay
""")
print(f"{'Date':<12} | {'Model':<14} | {'Purpose':<20} | {'Replay':<6} | {'Count':<5} | {'Tokens':<8} | {'Cost USD'}")
print("-" * 80)
total_live_cost = 0.0
total_live_calls = 0
for r in c.fetchall():
    dt, m, p, rep, cnt, tok, cost = r
    tok_str = str(tok) if tok is not None else "0"
    cost_val = cost if cost is not None else 0.0
    if rep == 0:
        total_live_cost += cost_val
        total_live_calls += cnt
    print(f"{dt:<12} | {m:<14} | {p:<20} | {str(rep):<6} | {cnt:<5} | {tok_str:<8} | ${cost_val:.4f}")

print("-" * 80)
print(f"Total live calls: {total_live_calls}, Total live cost: ${total_live_cost:.4f}")

