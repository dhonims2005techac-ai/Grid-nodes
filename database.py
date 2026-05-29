import sqlite3, datetime

DB = "grid_results.db"

def init():
    conn = sqlite3.connect(DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS results (
        job_id TEXT, timestamp TEXT, task TEXT,
        node TEXT, result TEXT, status TEXT, elapsed REAL
    )''')
    conn.commit()
    conn.close()

def save(job_id, task, node, result, status, elapsed):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?)",
                 (job_id, datetime.datetime.now().isoformat(),
                  task, node, str(result), status, elapsed))
    conn.commit()
    conn.close()

def history(limit=10):
    conn  = sqlite3.connect(DB)
    rows  = conn.execute(
        "SELECT job_id, timestamp, task, status, elapsed "
        "FROM results ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    if not rows:
        print("  No history yet.")
        return
    print(f"\n  {'Job ID':<10} {'Time':<20} {'Task':<12} {'Status':<12} Elapsed")
    print("  " + "-" * 62)
    for r in rows:
        print(f"  {r[0][:8]:<10} {r[1][:19]:<20} {r[2]:<12} {r[3]:<12} {r[4]:.2f}s")
