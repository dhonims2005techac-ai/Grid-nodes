"""
Distributed average, stats aggregation, and CSV analysis.
Separated from master.py following lean-software principles.
"""
import csv, time, uuid
import scheduler, node_manager

def distributed_average(results):
    total_sum, total_count = 0, 0
    for r in results:
        if r.get("status") == "completed":
            res = r.get("result", {})
            if isinstance(res, dict):
                total_sum   += res.get("sum", 0)
                total_count += res.get("count", 0)
            else:
                total_sum   += res
                total_count += 1
    return total_sum / total_count if total_count else 0

def aggregate_stats(results):
    completed = [r for r in results if r.get("status") == "completed"]
    sums   = [r["result"]["sum"]   for r in completed if isinstance(r.get("result"), dict)]
    counts = [r["result"]["count"] for r in completed if isinstance(r.get("result"), dict)]
    mins   = [r["result"]["min"]   for r in completed if isinstance(r.get("result"), dict)]
    maxs   = [r["result"]["max"]   for r in completed if isinstance(r.get("result"), dict)]
    if not sums:
        return None
    total = sum(sums)
    count = sum(counts)
    return {
        "sum": total, "count": count,
        "avg": total/count if count else 0,
        "min": min(mins), "max": max(maxs)
    }

def analyze_csv(filepath, online_nodes):
    try:
        with open(filepath) as f:
            reader  = csv.reader(f)
            headers = next(reader)
            rows    = list(reader)
    except Exception as e:
        print(f"❌ Cannot read CSV: {e}")
        return
    flat = []
    for row in rows:
        for cell in row:
            try: flat.append(float(cell.strip()))
            except: pass
    if not flat:
        print("❌ No numeric data found!")
        return
    print(f"\n📂 {len(rows)} rows | {len(headers)} columns | {len(flat):,} numeric values")
    chunks = scheduler.smart_chunk(flat, online_nodes)
    job_id = str(uuid.uuid4())
    t0     = time.time()
    results = scheduler.run("stats", chunks, online_nodes, job_id)
    elapsed = time.time() - t0
    agg = aggregate_stats(results)
    if agg:
        print(f"\n{'='*55}")
        print(f"  📊 CSV RESULTS")
        print(f"{'='*55}")
        print(f"  Values   : {agg['count']:,}")
        print(f"  Sum      : {agg['sum']:,.2f}")
        print(f"  Average  : {agg['avg']:.4f}")
        print(f"  Min      : {agg['min']:.2f}")
        print(f"  Max      : {agg['max']:.2f}")
        print(f"  Time     : {elapsed:.2f}s")
        print(f"  Ops/sec  : {round(agg['count']/elapsed):,}" if elapsed else "")
