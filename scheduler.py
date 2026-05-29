"""
scheduler.py — Task distribution with node weighting.
Fast nodes get bigger chunks. Slow nodes get smaller chunks.
"""
import requests, time, concurrent.futures, os
from node_manager import stats, record_success, record_failure

API_KEY     = os.environ.get("GRID_API_KEY")
MAX_RETRIES = 3

# ── STREAMING GENERATOR (no intermediate list) ───────────────
def generate_chunks(start, end, num_nodes):
    """Generator — never materializes full list in RAM"""
    size = max(1, (end - start) // num_nodes)
    i = start
    while i < end:
        yield list(range(i, min(i + size, end)))
        i += size

def smart_chunk(values, nodes):
    n    = min(len(values), len(nodes))
    size = max(1, len(values) // n)
    return [values[i:i+size] for i in range(0, len(values), size)]

# ── NODE WEIGHT CALCULATION ──────────────────────────────────
def get_node_weight(node):
    """
    Weight = how fast the node is relative to others.
    Faster nodes get higher weight = bigger chunks.
    New nodes with no data get weight 1.0 (neutral).
    """
    s = stats.get(node, {})
    if not s or s.get("calls", 0) == 0:
        return 1.0
    avg_time = s["total_time"] / s["calls"]
    if avg_time <= 0:
        return 1.0
    # Lower time = higher weight
    return 1.0 / avg_time

def weighted_chunk(values, online_nodes):
    """
    Distribute chunks proportional to node speed.
    Fast node = bigger chunk.
    Slow node = smaller chunk.
    """
    if not online_nodes:
        return []

    weights     = [get_node_weight(n) for n in online_nodes]
    total_weight = sum(weights)
    proportions  = [w / total_weight for w in weights]
    n_values     = len(values)

    chunks = []
    start  = 0
    for i, prop in enumerate(proportions):
        # Last node gets whatever remains
        if i == len(proportions) - 1:
            chunk = values[start:]
        else:
            size  = max(1, round(prop * n_values))
            chunk = values[start:start + size]
            start += size
        chunks.append(chunk)

    return chunks

# ── SEND TASK WITH RETRY ─────────────────────────────────────
def _send(node_url, task, values):
    headers = {"X-API-KEY": API_KEY}
    payload = {"task": task, "values": values}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            t0      = time.time()
            r       = requests.post(f"{node_url}/compute",
                                    json=payload, headers=headers, timeout=30)
            elapsed = time.time() - t0
            result  = r.json()
            if result.get("status") == "completed":
                record_success(node_url, elapsed)
                result.update({"elapsed": elapsed, "node_url": node_url})
                return result
            record_failure(node_url)
        except Exception as e:
            record_failure(node_url)
            if attempt < MAX_RETRIES:
                print(f"  ⚠️  Retry {attempt}/{MAX_RETRIES} → {node_url.split('//')[1][:30]}")
                time.sleep(1)
            else:
                return {"status": "failed", "error": str(e),
                        "node_url": node_url, "elapsed": 0}
    return {"status": "failed", "error": "Max retries exceeded",
            "node_url": node_url, "elapsed": 0}

# ── RUN TASK ─────────────────────────────────────────────────
def run(task, data_chunks, online_nodes, job_id):
    print(f"\n⚡ '{task}' → {len(online_nodes)} nodes  |  Job: {job_id[:8]}")
    results = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(online_nodes)) as ex:
        futures = {
            ex.submit(_send, node, task, chunk): node
            for node, chunk in zip(online_nodes, data_chunks)
        }
        for f in concurrent.futures.as_completed(futures):
            res    = f.result()
            node   = futures[f]
            status = res.get("status", "failed")
            emoji  = "✅" if status == "completed" else "❌"
            val    = res.get("result", "N/A")
            t      = res.get("elapsed", 0)
            short  = node.split("//")[1][:35]
            if isinstance(val, dict):
                val = " ".join(f"{k}={v}" for k, v in list(val.items())[:3])
            print(f"  {emoji} {short:<37} {val}  [{t:.2f}s]")
            results.append(res)
    return results

# ── PROCESS QUEUE ────────────────────────────────────────────
def process_queue(online_nodes):
    """Process all queued jobs one by one using weighted distribution"""
    import job_queue
    processed = 0
    while True:
        job = job_queue.next_job()
        if not job:
            break
        job_id = job["job_id"]
        task   = job["task"]
        values = job["values"]
        print(f"\n📋 Processing job {job_id[:8]}  task={task}")
        job_queue.mark_running(job_id)
        try:
            # Use weighted chunking — fast nodes get more work
            chunks  = weighted_chunk(values, online_nodes)
            results = run(task, chunks, online_nodes, job_id)
            completed = [r for r in results if r.get("status") == "completed"]
            if completed:
                job_queue.mark_done(job_id, str(len(completed)) + " nodes completed")
                processed += 1
            else:
                job_queue.mark_failed(job_id)
        except Exception as e:
            print(f"  ❌ Job failed: {e}")
            job_queue.mark_failed(job_id)
    return processed
