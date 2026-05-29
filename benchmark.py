"""
benchmark.py — Speed tests. Optional. Not loaded in production.
Streams chunks instead of materializing lists.
"""
import time, uuid, scheduler

def run_benchmark(online_nodes):
    print("🔥 Benchmark: 1M numbers (streamed)...")
    # Stream directly — no list() wrapper
    t0      = time.time()
    results = []
    for chunk in scheduler.generate_chunks(1, 1000001, len(online_nodes)):
        results.append(chunk)
    # Now distribute
    elapsed_chunk = time.time() - t0
    t0      = time.time()
    results = scheduler.run("sum", results, online_nodes, str(uuid.uuid4()))
    elapsed = time.time() - t0
    completed = [r for r in results if r.get("status") == "completed"]
    vals  = []
    for r in completed:
        res = r.get("result", {})
        v   = res.get("sum", res) if isinstance(res, dict) else res
        if isinstance(v, (int, float)): vals.append(v)
    total = sum(vals)
    ops   = round(1000000 / elapsed) if elapsed else 0
    print(f"\n  Result   : {total:,}")
    print(f"  Time     : {elapsed:.2f}s")
    print(f"  Ops/sec  : {ops:,}")

def run_stress(online_nodes, rounds=5):
    print(f"🔁 Stress test — {rounds} rounds (streamed)...")
    times = []
    for i in range(rounds):
        print(f"\n  Round {i+1}/{rounds}...")
        chunks  = list(scheduler.generate_chunks(1, 100001, len(online_nodes)))
        t0      = time.time()
        scheduler.run("sum", chunks, online_nodes, str(uuid.uuid4()))
        elapsed = time.time() - t0
        times.append(elapsed)
        print(f"  ⏱️  {elapsed:.2f}s")
    avg = sum(times) / len(times)
    print(f"\n  Rounds   : {rounds}")
    print(f"  Average  : {avg:.2f}s")
    print(f"  Fastest  : {min(times):.2f}s")
    print(f"  Slowest  : {max(times):.2f}s")
    print(f"  Ops/sec  : {round(100000/avg):,}")
