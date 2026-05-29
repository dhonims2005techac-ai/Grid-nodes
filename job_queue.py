"""
job_queue.py — Queue, priority, retry, and resume logic.
One responsibility: manage the job lifecycle.
"""
import sqlite3, uuid, datetime, json

DB = "grid_results.db"

PRIORITY_HIGH   = 1
PRIORITY_NORMAL = 2
PRIORITY_LOW    = 3

def init():
    conn = sqlite3.connect(DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS job_queue (
        job_id     TEXT PRIMARY KEY,
        task       TEXT,
        values_json TEXT,
        status     TEXT,
        priority   INTEGER,
        retries    INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 3,
        created_at TEXT,
        started_at TEXT,
        finished_at TEXT,
        result     TEXT
    )''')
    conn.commit()
    conn.close()

def enqueue(task, values, priority=PRIORITY_NORMAL, max_retries=3):
    job_id = str(uuid.uuid4())
    conn   = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO job_queue VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, task, json.dumps(values), "queued",
         priority, 0, max_retries,
         datetime.datetime.now().isoformat(), None, None, None)
    )
    conn.commit()
    conn.close()
    print(f"  📥 Queued job {job_id[:8]}  task={task}  priority={priority}")
    return job_id

def next_job():
    """Get highest priority queued job"""
    conn = sqlite3.connect(DB)
    row  = conn.execute(
        "SELECT * FROM job_queue WHERE status='queued' "
        "ORDER BY priority ASC, created_at ASC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "job_id": row[0], "task": row[1],
        "values": json.loads(row[2]),
        "priority": row[4], "retries": row[5],
        "max_retries": row[6]
    }

def mark_running(job_id):
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE job_queue SET status='running', started_at=? WHERE job_id=?",
        (datetime.datetime.now().isoformat(), job_id)
    )
    conn.commit()
    conn.close()

def mark_done(job_id, result):
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE job_queue SET status='completed', finished_at=?, result=? WHERE job_id=?",
        (datetime.datetime.now().isoformat(), str(result), job_id)
    )
    conn.commit()
    conn.close()

def mark_failed(job_id):
    conn = sqlite3.connect(DB)
    row  = conn.execute(
        "SELECT retries, max_retries FROM job_queue WHERE job_id=?", (job_id,)
    ).fetchone()
    if not row:
        conn.close()
        return
    retries, max_retries = row
    retries += 1
    if retries >= max_retries:
        conn.execute(
            "UPDATE job_queue SET status='failed', retries=?, finished_at=? WHERE job_id=?",
            (retries, datetime.datetime.now().isoformat(), job_id)
        )
        print(f"  ❌ Job {job_id[:8]} permanently failed after {retries} retries")
    else:
        conn.execute(
            "UPDATE job_queue SET status='queued', retries=? WHERE job_id=?",
            (retries, job_id)
        )
        print(f"  🔄 Job {job_id[:8]} requeued (attempt {retries+1}/{max_retries})")
    conn.commit()
    conn.close()

def resume_interrupted():
    """Requeue any jobs that were 'running' but never finished (interrupted)"""
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT job_id FROM job_queue WHERE status='running'"
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE job_queue SET status='queued' WHERE job_id=?", (row[0],)
        )
        print(f"  🔁 Resumed interrupted job: {row[0][:8]}")
    conn.commit()
    conn.close()
    return len(rows)

def show_queue(limit=15):
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT job_id, task, status, priority, retries, created_at, result "
        "FROM job_queue ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    if not rows:
        print("  Queue is empty.")
        return
    print(f"\n  {'Job ID':<10} {'Task':<12} {'Status':<12} {'Pri':<5} {'Retries':<8} {'Created':<20} Result")
    print("  " + "-" * 85)
    for r in rows:
        result_preview = str(r[6])[:15] if r[6] else "-"
        print(f"  {r[0][:8]:<10} {r[1]:<12} {r[2]:<12} {r[3]:<5} {r[4]:<8} {r[5][:19]:<20} {result_preview}")

def queue_stats():
    conn   = sqlite3.connect(DB)
    counts = dict(conn.execute(
        "SELECT status, COUNT(*) FROM job_queue GROUP BY status"
    ).fetchall())
    conn.close()
    return counts
