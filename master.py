"""
master.py — UI, orchestration, and queue management only.
"""
import os, uuid, datetime, time
import node_manager, scheduler, database, analytics, job_queue

API_KEY = os.environ.get("GRID_API_KEY")

def aggregate(task, results):
    completed = [r for r in results if r.get("status") == "completed"]
    if task == "average":
        return analytics.distributed_average(completed)
    elif task == "stats":
        return analytics.aggregate_stats(completed)
    elif task == "primes":
        all_p = []
        for r in completed:
            res = r.get("result", {})
            if isinstance(res, dict):
                all_p.extend(res.get("primes", []))
        all_p.sort()
        print(f"  First 10: {all_p[:10]}")
        return f"{len(all_p)} primes found"
    else:
        vals = []
        for r in completed:
            res = r.get("result", {})
            v   = res.get("sum", res) if isinstance(res, dict) else res
            if isinstance(v, (int, float)): vals.append(v)
        if task == "multiply":
            result = 1
            for v in vals: result *= v
            return result
        return sum(vals)

def get_values_input():
    try:
        nums   = input("Numbers (comma separated):\n> ")
        values = [float(x.strip()) for x in nums.split(",")]
        return values
    except:
        print("❌ Invalid input!")
        return None

if __name__ == '__main__':
    database.init()
    job_queue.init()

    print("=" * 55)
    print("     ⚡ GRID MASTER CONTROLLER v6 ⚡")
    print("=" * 55)
    print(f"  🕐 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  🌐 {len(node_manager.NODES)} nodes configured")
    print(f"  🔑 {'✅ API Key Active' if API_KEY else '❌ No API Key!'}")

    # Resume any interrupted jobs from last session
    resumed = job_queue.resume_interrupted()
    if resumed:
        print(f"  🔁 Resumed {resumed} interrupted jobs")

    node_manager.check_all()

    while True:
        print("\n" + "=" * 55)
        print("           GRID MENU")
        print("=" * 55)
        print("  1.  Submit Task (run immediately)")
        print("  2.  Queue Task  (add to job queue)")
        print("  3.  Process Queue")
        print("  4.  View Queue")
        print("  5.  Node Status")
        print("  6.  Performance Ranking")
        print("  7.  Job History")
        print("  8.  Analyze CSV")
        print("  9.  Benchmark / Stress Test")
        print("  0.  Exit")

        choice = input("\nEnter choice: ").strip()

        # ── NODE STATUS ──────────────────────────────────────
        if choice == "5":
            node_manager.check_all()

        # ── PERFORMANCE RANKING ──────────────────────────────
        elif choice == "6":
            node_manager.show_ranking()

        # ── JOB HISTORY ──────────────────────────────────────
        elif choice == "7":
            database.history()

        # ── CSV ANALYSIS ─────────────────────────────────────
        elif choice == "8":
            online = node_manager.get_online_nodes()
            if not online:
                print("❌ No nodes available!")
                continue
            fp = input("CSV file path:\n> ").strip()
            analytics.analyze_csv(fp, online)

        # ── BENCHMARK ────────────────────────────────────────
        elif choice == "9":
            online = node_manager.get_online_nodes()
            if not online:
                print("❌ No nodes available!")
                continue
            print("\n  1. Benchmark  2. Stress Test")
            b = input("Choice: ").strip()
            import benchmark
            if b == "1":
                benchmark.run_benchmark(online)
            elif b == "2":
                r = input("Rounds (default 5): ").strip()
                benchmark.run_stress(online, int(r) if r.isdigit() else 5)

        # ── VIEW QUEUE ───────────────────────────────────────
        elif choice == "4":
            job_queue.show_queue()
            stats = job_queue.queue_stats()
            print(f"\n  Queue stats: {stats}")

        # ── PROCESS QUEUE ────────────────────────────────────
        elif choice == "3":
            online = node_manager.get_online_nodes()
            if not online:
                print("❌ No nodes available!")
                continue
            stats  = job_queue.queue_stats()
            queued = stats.get("queued", 0)
            if queued == 0:
                print("  Queue is empty.")
                continue
            print(f"\n📋 Processing {queued} queued jobs...")
            done = scheduler.process_queue(online)
            print(f"\n✅ Processed {done} jobs.")

        # ── QUEUE TASK ───────────────────────────────────────
        elif choice == "2":
            tasks = {"1": "sum", "2": "multiply",
                     "3": "average", "4": "stats", "5": "primes"}
            print("\n  1.Sum  2.Multiply  3.Average  4.Stats  5.Primes")
            t    = input("Task: ").strip()
            task = tasks.get(t)
            if not task:
                print("❌ Invalid task!")
                continue
            values = get_values_input()
            if values is None:
                continue
            print("\n  1.High  2.Normal  3.Low")
            p = input("Priority (default 2): ").strip()
            priority = {"1": 1, "2": 2, "3": 3}.get(p, 2)
            jid = job_queue.enqueue(task, values, priority)
            print(f"  ✅ Job {jid[:8]} added to queue!")

        # ── SUBMIT IMMEDIATELY ───────────────────────────────
        elif choice == "1":
            tasks = {"1": "sum", "2": "multiply",
                     "3": "average", "4": "stats", "5": "primes"}
            print("\n  1.Sum  2.Multiply  3.Average  4.Stats  5.Primes")
            t    = input("Task: ").strip()
            task = tasks.get(t)
            if not task:
                print("❌ Invalid task!")
                continue

            online = node_manager.get_online_nodes()
            if not online:
                print("❌ No nodes available!")
                continue

            if task == "primes":
                try:
                    rng  = input("Range (start,end):\n> ")
                    s, e = [int(x.strip()) for x in rng.split(",")]
                    chunks = list(scheduler.generate_chunks(s, e, len(online)))
                except:
                    print("❌ Invalid range!")
                    continue
            else:
                values = get_values_input()
                if values is None:
                    continue
                # Use weighted chunking — fast nodes get more work
                chunks = scheduler.weighted_chunk(values, online)

            job_id = str(uuid.uuid4())
            t0     = time.time()
            results = scheduler.run(task, chunks, online, job_id)
            elapsed = time.time() - t0

            completed = [r for r in results if r.get("status") == "completed"]
            failed    = [r for r in results if r.get("status") != "completed"]
            total     = len(completed) + len(failed)
            final     = aggregate(task, results)

            for r in results:
                database.save(job_id, task,
                              r.get("node_url", "?"),
                              str(r.get("result", "")),
                              r.get("status", "failed"),
                              r.get("elapsed", 0))

            print(f"\n{'='*55}")
            print(f"  🎯 RESULT       : {final}")
            print(f"  ✅ Completed    : {len(completed)}/{total}")
            print(f"  ⏱️  Time         : {elapsed:.2f}s")
            print(f"  🏆 Success Rate : {round(len(completed)/total*100) if total else 0}%")
            print(f"  🔖 Job ID       : {job_id[:8]}")
            print(f"{'='*55}")

        # ── EXIT ─────────────────────────────────────────────
        elif choice == "0":
            print("\n👋 Shutting down...")
            node_manager.show_ranking()
            stats = job_queue.queue_stats()
            if stats.get("queued", 0) > 0:
                print(f"  ⚠️  {stats['queued']} jobs still in queue!")
            print(f"🕐 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            break

        else:
            print("❌ Invalid choice!")
