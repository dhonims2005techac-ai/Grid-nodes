import requests, time

BLACKLIST_THRESHOLD = 3
BLACKLIST_DURATION  = 300   # 5 minutes

NODES = [
    "https://grid-nodes.onrender.com",
    "https://grid-nodes2.onrender.com",
    "https://grid-nodes3.onrender.com",
    "https://grid-nodes4.onrender.com",
    "https://grid-nodesv2.onrender.com",
    "https://grid-nodesv2-1.onrender.com",
    "https://grid-nodesr2-7.onrender.com",
    "https://grid-nodesr8.onrender.com",
    "https://grid-nodes9.onrender.com",
    "https://grid-nodes10.onrender.com",
    "https://grid-nodes11.onrender.com",
    "https://grid-nodes12.onrender.com",
    "https://bug-spy1-grid222.hf.space",
    "https://dhoni22-girdtest.hf.space",
    "https://done1237-gridc.hf.space",
    "https://dhonims-grid333.hf.space",
    "https://bug-spy1-gridnodehf5.hf.space",
    "https://bug-spy1-gridnodehf6.hf.space",
    "https://dhoni22-gridnodehf7.hf.space",
    "https://dhoni22-gridnodehf8.hf.space",
    "https://done1237-gridnodehf9.hf.space",
    "https://done1237-gridnodehf10.hf.space",
    "https://dhonims-gridnodehf11.hf.space",
    "https://dhonims-grid12.hf.space",
]

stats = {n: {"success": 0, "failures": 0, "total_time": 0.0,
             "calls": 0, "blacklisted_until": 0} for n in NODES}

def is_blacklisted(node):
    until = stats[node]["blacklisted_until"]
    if until == 0: return False
    if time.time() < until: return True
    stats[node]["blacklisted_until"] = 0
    print(f"  🔓 Blacklist lifted: {node.split('//')[1][:35]}")
    return False

def record_success(node, elapsed):
    s = stats[node]
    s["success"] += 1
    s["failures"] = 0
    s["calls"]    += 1
    s["total_time"] += elapsed

def record_failure(node):
    s = stats[node]
    s["failures"] += 1
    s["calls"]    += 1
    if s["failures"] >= BLACKLIST_THRESHOLD:
        s["blacklisted_until"] = time.time() + BLACKLIST_DURATION
        print(f"  🔴 Blacklisted {BLACKLIST_DURATION//60}min: {node.split('//')[1][:35]}")

def is_online(url):
    if is_blacklisted(url):
        remaining = round(stats[url]["blacklisted_until"] - time.time())
        print(f"  🔴 BLACKLISTED ({remaining}s)  {url.split('//')[1][:35]}")
        return False
    try:
        start = time.time()
        r = requests.get(f"{url}/health", timeout=10)
        elapsed = time.time() - start
        if r.status_code == 200:
            print(f"  ✅ ONLINE  [{elapsed:.2f}s]  {url}")
            return True
        print(f"  ❌ OFFLINE         {url}")
        return False
    except:
        print(f"  ❌ OFFLINE         {url}")
        return False

def get_online_nodes():
    return [n for n in NODES if is_online(n)]

def check_all():
    print("\n🔍 Checking all nodes...\n")
    online = sum(1 for n in NODES if is_online(n))
    print(f"\n📊 {online}/{len(NODES)} online  |  Health: {round(online/len(NODES)*100)}%")
    return online

def show_ranking():
    ranked = []
    for node, s in stats.items():
        if s["calls"] > 0:
            avg  = s["total_time"] / s["calls"]
            rate = round(s["success"] / s["calls"] * 100)
            bl   = "🔴" if is_blacklisted(node) else "  "
            ranked.append((node, avg, rate, s["success"], s["failures"], bl))
    if not ranked:
        print("  No data yet.")
        return
    ranked.sort(key=lambda x: x[1])
    print(f"\n  {'#':<4} {'Node':<38} {'Avg':<9} {'OK%':<7} {'OK':<5} FAIL")
    print("  " + "-" * 68)
    medals = ["🥇", "🥈", "🥉"]
    for i, (node, avg, rate, ok, fail, bl) in enumerate(ranked, 1):
        m = medals[i-1] if i <= 3 else f" {i}."
        print(f"  {m:<4} {node.split('//')[1][:36]:<38} {avg:.2f}s  {rate}%   {ok:<5} {fail} {bl}")

def show_blacklist():
    bl = [(n, round(stats[n]["blacklisted_until"] - time.time()))
          for n in NODES if is_blacklisted(n)]
    if not bl:
        print("  ✅ No nodes blacklisted.")
        return
    for node, rem in bl:
        print(f"  🔴 {node.split('//')[1][:40]}  ({rem}s remaining)")
