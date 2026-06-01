"""
Grid Master Dashboard V4 — CYBER OPERATIONS CENTER
Dark red lightning theme.
Features: Digital Twin, Live Alerts, Node Leaderboard,
          Historical Analytics, AI Failure Prediction
"""
from flask import Flask, jsonify, render_template_string, request
import sqlite3, datetime, os, sys, time, json, csv, io, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__)
API_KEY = os.environ.get("GRID_API_KEY", "")
DB = "grid_results.db"

RENDER_NODES = [
    "https://grid-nodes.onrender.com","https://grid-nodes2.onrender.com",
    "https://grid-nodes3.onrender.com","https://grid-nodes4.onrender.com",
    "https://grid-nodesv2.onrender.com","https://grid-nodesv2-1.onrender.com",
    "https://grid-nodesr2-7.onrender.com","https://grid-nodesr8.onrender.com",
    "https://grid-nodes9.onrender.com","https://grid-nodes10.onrender.com",
    "https://grid-nodes11.onrender.com","https://grid-nodes12.onrender.com",
]
HF_NODES = [
    "https://bug-spy1-grid222.hf.space","https://dhoni22-girdtest.hf.space",
    "https://done1237-gridc.hf.space","https://dhonims-grid333.hf.space",
    "https://bug-spy1-gridnodehf5.hf.space","https://bug-spy1-gridnodehf6.hf.space",
    "https://dhoni22-gridnodehf7.hf.space","https://dhoni22-gridnodehf8.hf.space",
    "https://done1237-gridnodehf9.hf.space","https://done1237-gridnodehf10.hf.space",
    "https://dhonims-gridnodehf11.hf.space","https://dhonims-grid12.hf.space",
]
ALL_NODES = RENDER_NODES + HF_NODES

security_log  = {"unauthorized": 0, "rate_limits": 0, "requests": 0, "attacks": 0}
throughput_log = []
alerts = []  # live alert feed

def add_alert(msg, level="info"):
    alerts.insert(0, {"msg": msg, "level": level,
                       "time": datetime.datetime.now().strftime("%H:%M:%S")})
    if len(alerts) > 30:
        alerts.pop()

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def node_perf_map():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT node, AVG(elapsed) as avg_e, COUNT(*) as total, "
            "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as ok "
            "FROM results GROUP BY node"
        ).fetchall()
        conn.close()
        return {r["node"]: dict(r) for r in rows}
    except:
        return {}

def queue_stats():
    try:
        conn = get_db()
        rows = conn.execute("SELECT status, COUNT(*) as c FROM job_queue GROUP BY status").fetchall()
        conn.close()
        return {r["status"]: r["c"] for r in rows}
    except:
        return {}

def recent_jobs(limit=20):
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT job_id, timestamp, task, node, status, elapsed, result "
            "FROM results ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except:
        return []

def job_queue_list(limit=15):
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT job_id, task, status, priority, retries, created_at, result "
            "FROM job_queue ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except:
        return []

def historical_latency():
    """Last 20 job averages for the chart"""
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT AVG(elapsed) as avg_e, COUNT(*) as cnt, "
            "substr(timestamp,12,5) as t "
            "FROM results WHERE status='completed' "
            "GROUP BY substr(timestamp,1,16) "
            "ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()
        conn.close()
        rows = list(reversed(rows))
        return {
            "labels": [r["t"] or "--" for r in rows],
            "render": [round(r["avg_e"] or 0, 3) for r in rows],
        }
    except:
        return {"labels": [], "render": []}

def db_stats():
    try:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        size  = os.path.getsize(DB) if os.path.exists(DB) else 0
        conn.close()
        return {"records": total, "size_kb": round(size / 1024, 1)}
    except:
        return {"records": 0, "size_kb": 0}

def ai_analytics():
    perf  = node_perf_map()
    valid = [(n, d) for n, d in perf.items() if d.get("total", 0) > 0]
    if not valid:
        return {"fastest": "N/A", "fastest_t": 0, "slowest": "N/A", "slowest_t": 0,
                "avg_response": 0, "predicted_failures": 0, "total_ops": 0,
                "success_rate": 0, "render_avg": 0, "hf_avg": 0,
                "leaderboard": [], "failure_risks": []}
    by_spd = sorted(valid, key=lambda x: x[1].get("avg_e") or 99)
    total_ops = sum(d.get("total", 0) for _, d in valid)
    total_ok  = sum(d.get("ok",    0) for _, d in valid)
    avg_r     = sum(d.get("avg_e", 0) for _, d in valid) / len(valid)
    r_nodes   = [(n, d) for n, d in valid if "onrender" in n]
    h_nodes   = [(n, d) for n, d in valid if "hf.space"  in n]
    r_avg     = sum(d.get("avg_e", 0) for _, d in r_nodes) / len(r_nodes) if r_nodes else 0
    h_avg     = sum(d.get("avg_e", 0) for _, d in h_nodes) / len(h_nodes) if h_nodes else 0

    # Leaderboard top 8
    lb = []
    for i, (n, d) in enumerate(by_spd[:8]):
        rate = round(d.get("ok", 0) / d["total"] * 100) if d["total"] else 0
        lb.append({
            "rank": i + 1,
            "name": n.replace("https://", "").split(".")[0][:20],
            "avg":  round(d.get("avg_e", 0), 3),
            "rate": rate,
            "total": d["total"],
        })

    # Failure risk prediction
    risks = []
    for n, d in valid:
        if d["total"] < 2:
            continue
        rate     = d.get("ok", 0) / d["total"]
        avg_lat  = d.get("avg_e", 0) or 0
        score    = 0
        reasons  = []
        if rate < 0.7:
            score += 40
            reasons.append("Low success rate")
        if avg_lat > 2.0:
            score += 30
            reasons.append("High latency")
        if d["total"] - d.get("ok", 0) >= 3:
            score += 30
            reasons.append("Multiple failures")
        if score > 30:
            risks.append({
                "name":    n.replace("https://", "").split(".")[0][:20],
                "risk":    min(score, 99),
                "reasons": reasons,
            })
    risks.sort(key=lambda x: -x["risk"])

    return {
        "fastest":            by_spd[0][0].replace("https://", "").split(".")[0][:18],
        "fastest_t":          round(by_spd[0][1].get("avg_e", 0), 3),
        "slowest":            by_spd[-1][0].replace("https://", "").split(".")[0][:18],
        "slowest_t":          round(by_spd[-1][1].get("avg_e", 0), 3),
        "avg_response":       round(avg_r, 3),
        "predicted_failures": len(risks),
        "total_ops":          total_ops,
        "success_rate":       round(total_ok / total_ops * 100) if total_ops else 0,
        "render_avg":         round(r_avg, 3),
        "hf_avg":             round(h_avg, 3),
        "render_success":     round(sum(d.get("ok",0) for _,d in r_nodes)/max(sum(d.get("total",0) for _,d in r_nodes),1)*100),
        "hf_success":         round(sum(d.get("ok",0) for _,d in h_nodes)/max(sum(d.get("total",0) for _,d in h_nodes),1)*100),
        "leaderboard":        lb,
        "failure_risks":      risks[:5],
    }

def grid_ai_query(q):
    q    = q.lower().strip()
    perf = node_perf_map()
    ai   = ai_analytics()
    valid = [(n, d) for n, d in perf.items() if d.get("total", 0) > 0]

    if any(w in q for w in ["fastest", "best", "quickest"]):
        lb = ai.get("leaderboard", [])
        if lb:
            top = lb[0]
            return f"🏆 <b>Fastest: {top['name']}</b><br>Latency: {top['avg']}s | Success: {top['rate']}% | Jobs: {top['total']}"
        return "No data yet."

    elif any(w in q for w in ["predict", "fail", "risk", "danger"]):
        risks = ai.get("failure_risks", [])
        if not risks:
            return "✅ No nodes at risk right now."
        lines = [f"⚠ <b>{r['name']}</b> — {r['risk']}% risk<br>" + ", ".join(r["reasons"]) for r in risks]
        return "🔴 <b>Failure Predictions:</b><br>" + "<br>".join(lines)

    elif any(w in q for w in ["compare", "render vs", "hf vs", "which cluster"]):
        return (f"📊 <b>Cluster Comparison:</b><br>"
                f"🖥 Render — Avg: {ai['render_avg']}s | Success: {ai['render_success']}%<br>"
                f"🤗 HuggingFace — Avg: {ai['hf_avg']}s | Success: {ai['hf_success']}%<br>"
                f"{'🖥 Render' if ai['render_avg'] < ai['hf_avg'] else '🤗 HuggingFace'} is currently faster.")

    elif any(w in q for w in ["slow", "slowest", "worst"]):
        return f"🐢 <b>Slowest: {ai['slowest']}</b><br>Avg latency: {ai['slowest_t']}s"

    elif any(w in q for w in ["leaderboard", "ranking", "top"]):
        lb = ai.get("leaderboard", [])
        medals = ["🥇","🥈","🥉","4.","5.","6.","7.","8."]
        return "<b>Node Leaderboard:</b><br>" + "<br>".join(
            f"{medals[i]} {r['name']} — {r['avg']}s | {r['rate']}%"
            for i, r in enumerate(lb)
        ) if lb else "No data yet."

    elif any(w in q for w in ["health", "status", "how is"]):
        h = round(len([n for n in ALL_NODES if perf.get(n,{}).get("total",0)>0]) / len(ALL_NODES) * 100)
        return (f"💓 <b>Grid Health: {h}%</b><br>"
                f"Render: {ai['render_success']}% success<br>"
                f"HF: {ai['hf_success']}% success<br>"
                f"Avg response: {ai['avg_response']}s")

    elif any(w in q for w in ["failed", "error", "failed jobs"]):
        try:
            conn = get_db()
            rows = conn.execute(
                "SELECT job_id, task, node, timestamp FROM results "
                "WHERE status='failed' ORDER BY timestamp DESC LIMIT 5"
            ).fetchall()
            conn.close()
            if not rows:
                return "✅ No failures found!"
            return "❌ <b>Recent failures:</b><br>" + "<br>".join(
                f"• {r['job_id'][:7]} | {r['task']} | {(r['node'] or '').replace('https://','').split('.')[0][:18]}"
                for r in rows
            )
        except:
            return "Error reading DB."

    elif any(w in q for w in ["queue", "queued", "jobs"]):
        qs = queue_stats()
        return "📋 <b>Queue:</b><br>" + "<br>".join(f"• {s}: {c}" for s, c in qs.items()) if qs else "Queue is empty."

    elif any(w in q for w in ["security", "attack", "unauthorized"]):
        return (f"🔐 <b>Security:</b><br>"
                f"Unauthorized: {security_log['unauthorized']}<br>"
                f"Requests: {security_log['requests']}<br>"
                f"API Key: {'ACTIVE' if API_KEY else 'NOT SET'}")

    elif any(w in q for w in ["recommend", "remove", "which node"]):
        risks = ai.get("failure_risks", [])
        lb    = ai.get("leaderboard", [])
        rec   = []
        if risks:
            rec.append(f"⚠ Consider removing: <b>{risks[0]['name']}</b> ({risks[0]['risk']}% failure risk)")
        if lb:
            rec.append(f"✅ Best node to keep: <b>{lb[0]['name']}</b> ({lb[0]['avg']}s avg)")
        return "<br>".join(rec) if rec else "Not enough data for recommendations."

    elif any(w in q for w in ["help", "commands", "what can"]):
        return ("💡 <b>Commands:</b><br>"
                "• fastest node<br>• slowest node<br>• predict failures<br>"
                "• compare clusters<br>• node leaderboard<br>"
                "• grid health<br>• failed jobs<br>• security status<br>"
                "• recommend node removal<br>• queue status")
    else:
        return f"🤖 Unknown: <i>\"{q}\"</i><br>Type <b>help</b> for commands."

# ── MIDDLEWARE ───────────────────────────────────────────────
@app.before_request
def track():
    security_log["requests"] += 1
    key = request.headers.get("X-API-KEY", "")
    if request.path.startswith("/api/submit") and key != API_KEY and API_KEY:
        security_log["unauthorized"] += 1
        add_alert(f"Unauthorized request from {request.remote_addr}", "danger")

# ── API ROUTES ───────────────────────────────────────────────
@app.route('/api/dashboard')
def api_dashboard():
    perf   = node_perf_map()
    qs     = queue_stats()
    jobs   = recent_jobs(5)
    queue  = job_queue_list()
    ai     = ai_analytics()
    hist   = historical_latency()
    dbst   = db_stats()
    tpm    = len([t for t in throughput_log if time.time() - t < 60])
    total_j = sum(d.get("total", 0) for d in perf.values())

    nodes_status = {}
    for n in ALL_NODES:
        d     = perf.get(n, {})
        total = d.get("total", 0)
        ok    = d.get("ok",    0)
        rate  = round(ok / total * 100) if total else 0
        avg   = d.get("avg_e", 0) or 0
        # Heatmap color: green=fast ok, yellow=slow, red=failing, gray=unknown
        if total == 0:
            color = "unknown"
        elif rate >= 80 and avg < 1.0:
            color = "healthy"
        elif rate >= 60 or avg < 2.0:
            color = "slow"
        else:
            color = "failing"
        nodes_status[n] = {
            "name":   n.replace("https://", "").split(".")[0][:20],
            "rate":   rate, "avg": round(avg, 3),
            "total":  total, "online": total > 0,
            "color":  color,
        }

    online = len([n for n in ALL_NODES if nodes_status[n]["online"]])
    r_on   = len([n for n in RENDER_NODES if nodes_status[n]["online"]])
    h_on   = len([n for n in HF_NODES    if nodes_status[n]["online"]])

    return jsonify({
        "stats": {
            "online": online, "total": len(ALL_NODES),
            "jobs": total_j, "queued": qs.get("queued", 0),
            "health": round(online / len(ALL_NODES) * 100),
            "tpm": tpm, "render_on": r_on, "hf_on": h_on,
        },
        "nodes": nodes_status, "queue": qs, "jobs": jobs,
        "queue_list": queue[:10], "ai": ai,
        "security": security_log,
        "alerts": alerts[:10],
        "history": hist,
        "db": dbst,
    })

@app.route('/api/alerts')
def api_alerts():
    return jsonify(alerts[:15])

@app.route('/api/ai', methods=['POST'])
def api_ai():
    q = (request.json or {}).get("query", "")
    return jsonify({"response": grid_ai_query(q)})

@app.route('/api/submit', methods=['POST'])
def api_submit():
    data   = request.json or {}
    task   = data.get("task", "sum")
    values = data.get("values", [])
    if not values:
        return jsonify({"error": "No values"}), 400
    try:
        import scheduler, node_manager, database, analytics
        import uuid
        online  = node_manager.get_online_nodes()
        if not online:
            return jsonify({"error": "No nodes online"}), 503
        chunks  = scheduler.weighted_chunk(values, online)
        job_id  = str(uuid.uuid4())
        t0      = time.time()
        results = scheduler.run(task, chunks, online, job_id)
        elapsed = time.time() - t0
        completed = [r for r in results if r.get("status") == "completed"]
        if task == "average":
            final = analytics.distributed_average(completed)
        elif task == "stats":
            final = str(analytics.aggregate_stats(completed))
        else:
            vals = []
            for r in completed:
                res = r.get("result", {})
                v   = res.get("sum", res) if isinstance(res, dict) else res
                if isinstance(v, (int, float)):
                    vals.append(v)
            final = sum(vals)
        for r in results:
            database.save(job_id, task, r.get("node_url", "?"),
                          str(r.get("result", "")), r.get("status", "failed"),
                          r.get("elapsed", 0))
        throughput_log.append(time.time())
        add_alert(f"Job {job_id[:7]} completed — {len(completed)}/{len(results)} nodes", "success")
        return jsonify({"job_id": job_id[:8], "result": str(final),
                        "completed": len(completed), "total": len(results),
                        "elapsed": round(elapsed, 2)})
    except Exception as e:
        add_alert(f"Job failed: {str(e)[:40]}", "danger")
        return jsonify({"error": str(e)}), 500

@app.route('/api/csv', methods=['POST'])
def api_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files['file']
    content = f.read().decode('utf-8')
    reader  = csv.reader(io.StringIO(content))
    try:
        headers = next(reader)
    except:
        return jsonify({"error": "Empty CSV"}), 400
    rows = list(reader)
    flat = []
    for row in rows:
        for cell in row:
            try:
                flat.append(float(cell.strip()))
            except:
                pass
    if not flat:
        return jsonify({"error": "No numeric data"}), 400
    try:
        import scheduler, node_manager, database, analytics
        import uuid
        online  = node_manager.get_online_nodes()
        if not online:
            return jsonify({"error": "No nodes"}), 503
        chunks  = scheduler.smart_chunk(flat, online)
        job_id  = str(uuid.uuid4())
        t0      = time.time()
        results = scheduler.run("stats", chunks, online, job_id)
        elapsed = time.time() - t0
        completed = [r for r in results if r.get("status") == "completed"]
        agg = analytics.aggregate_stats(completed)
        add_alert(f"CSV analyzed — {len(rows)} rows, {len(flat)} values", "info")
        return jsonify({"rows": len(rows), "cols": len(headers),
                        "values": len(flat), "stats": agg,
                        "elapsed": round(elapsed, 2), "job_id": job_id[:8]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def dashboard():
    return render_template_string(HTML)

# ── HTML ─────────────────────────────────────────────────────
HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>GRID MASTER V4 — CYBER OPS CENTER</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
:root{
  --bg:#0a0000;--bg2:#110000;--bg3:#180000;
  --red:#ff1a1a;--red2:#cc0000;--red3:#880000;--red4:#440000;
  --crimson:#dc143c;--blood:#8b0000;
  --orange:#ff4400;--amber:#ff6600;
  --green:#00ff41;--cyan:#00e5ff;--yellow:#ffd700;
  --text:#ff9999;--muted:#883333;--dim:#441111;
  --border:#330000;--brd2:#4d0000;
  --glow:0 0 16px rgba(255,26,26,0.4);
  --glow2:0 0 30px rgba(220,20,60,0.3);
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{width:100%;min-height:100vh;}
body{background:var(--bg);color:var(--text);font-family:'Rajdhani',sans-serif;font-size:13px;overflow-x:hidden;}

/* LIGHTNING SCANLINES */
body::after{content:'';position:fixed;inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(255,0,0,0.04) 2px,rgba(255,0,0,0.04) 4px);
  pointer-events:none;z-index:9999;}

/* HEX GRID */
body::before{content:'';position:fixed;inset:0;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='100'%3E%3Cpath d='M28 66L0 50V18L28 2l28 16v32z' fill='none' stroke='%23ff1a1a' stroke-opacity='0.04' stroke-width='1'/%3E%3Cpath d='M28 100L0 84V52l28-16 28 16v32z' fill='none' stroke='%23ff1a1a' stroke-opacity='0.04' stroke-width='1'/%3E%3C/svg%3E");
  pointer-events:none;z-index:0;}

/* LIGHTNING BOLT DECORATION */
@keyframes lightning{0%,90%,100%{opacity:0}91%,94%{opacity:1}92%,95%{opacity:0.3}}

/* HEADER */
header{position:sticky;top:0;z-index:200;
  background:rgba(10,0,0,0.97);
  border-bottom:2px solid var(--red3);
  padding:8px 16px;display:flex;align-items:center;gap:12px;
  box-shadow:0 2px 30px rgba(255,26,26,0.25);}
.logo{font-family:'Orbitron',monospace;font-weight:900;font-size:22px;
  color:var(--red);letter-spacing:4px;
  text-shadow:0 0 20px rgba(255,26,26,0.8),0 0 40px rgba(255,26,26,0.4);
  flex-shrink:0;}
.v4badge{font-family:'Share Tech Mono',monospace;font-size:9px;
  letter-spacing:2px;color:var(--crimson);border:1px solid var(--red3);
  padding:2px 6px;background:rgba(220,20,60,0.1);}
.pill{border:1px solid var(--red3);padding:3px 9px;
  font-family:'Share Tech Mono',monospace;font-size:10px;letter-spacing:1px;
  display:flex;align-items:center;gap:5px;background:rgba(255,26,26,0.04);}
.dp{width:7px;height:7px;border-radius:50%;
  background:var(--green);box-shadow:0 0 7px var(--green);
  animation:blink 1.5s infinite;}
.dp-red{background:var(--red);box-shadow:0 0 7px var(--red);}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}
.hr{margin-left:auto;display:flex;align-items:center;gap:12px;}
.clock{font-family:'Orbitron',monospace;font-size:16px;
  color:var(--red);letter-spacing:2px;text-shadow:var(--glow);}
.lupd{font-family:'Share Tech Mono',monospace;font-size:9px;
  color:var(--muted);letter-spacing:1px;}
.rbtn{border:1px solid var(--red3);background:transparent;
  color:var(--red);font-family:'Rajdhani',sans-serif;font-weight:700;
  font-size:11px;padding:5px 12px;cursor:pointer;letter-spacing:2px;transition:all 0.15s;}
.rbtn:hover{background:rgba(255,26,26,0.1);box-shadow:var(--glow);}

/* LAYOUT */
main{position:relative;z-index:1;padding:10px 14px;max-width:1600px;margin:0 auto;}

/* PANEL */
.panel{background:var(--bg2);border:1px solid var(--brd2);position:relative;overflow:hidden;}
.panel::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,var(--red3),var(--crimson),var(--red3),transparent);}
.panel::after{content:'';position:absolute;bottom:0;right:0;
  width:10px;height:10px;border-bottom:2px solid var(--red3);border-right:2px solid var(--red3);}
.ph{padding:6px 11px;border-bottom:1px solid var(--brd2);
  display:flex;align-items:center;justify-content:space-between;
  background:rgba(255,26,26,0.025);}
.pt{font-family:'Rajdhani',sans-serif;font-weight:700;font-size:11px;
  letter-spacing:3px;text-transform:uppercase;color:var(--red);}
.pm{font-family:'Share Tech Mono',monospace;font-size:9px;
  color:var(--muted);letter-spacing:1px;}
.pb{padding:9px 11px;}

/* STAT CARDS */
.s6{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:8px;}
@media(max-width:1100px){.s6{grid-template-columns:repeat(3,1fr);}}
@media(max-width:600px){.s6{grid-template-columns:repeat(2,1fr);}}
.sc{background:var(--bg2);border:1px solid var(--brd2);
  padding:10px 12px;position:relative;overflow:hidden;}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--red3),var(--crimson),var(--red3));}
.sc::after{content:'';position:absolute;bottom:0;right:0;
  width:10px;height:10px;border-bottom:2px solid var(--red3);border-right:2px solid var(--red3);}
.sci{position:absolute;top:10px;right:10px;font-size:18px;opacity:0.15;}
.scl{font-family:'Share Tech Mono',monospace;font-size:9px;
  letter-spacing:1.5px;color:var(--muted);text-transform:uppercase;margin-bottom:4px;}
.scv{font-family:'Orbitron',monospace;font-size:24px;font-weight:700;
  color:var(--red);text-shadow:0 0 14px rgba(255,26,26,0.6);line-height:1;margin-bottom:3px;}
.scs{font-family:'Share Tech Mono',monospace;font-size:9px;
  color:var(--muted);margin-bottom:5px;}
.prog{background:var(--border);height:3px;}
.progf{height:100%;background:linear-gradient(90deg,var(--red3),var(--crimson));transition:width 0.6s;}

/* GRID LAYOUTS */
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:8px;}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;}
.g21{display:grid;grid-template-columns:2fr 1fr;gap:8px;margin-bottom:8px;}
.g12{display:grid;grid-template-columns:1fr 2fr;gap:8px;margin-bottom:8px;}
@media(max-width:1000px){.g3,.g2,.g21,.g12{grid-template-columns:1fr;}}

/* DIGITAL TWIN NODE MAP */
.twin-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:4px;}
.twin-node{
  aspect-ratio:1;border:1px solid var(--brd2);
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;font-family:'Share Tech Mono',monospace;
  font-size:8px;padding:2px;cursor:default;position:relative;
  transition:all 0.3s;overflow:hidden;}
.twin-node::after{content:'';position:absolute;inset:0;
  background:radial-gradient(circle,rgba(255,255,255,0.05) 0%,transparent 70%);
  opacity:0;transition:opacity 0.3s;}
.twin-node:hover::after{opacity:1;}
/* States */
.tn-healthy{background:rgba(0,255,65,0.06);border-color:rgba(0,255,65,0.3);}
.tn-slow{background:rgba(255,165,0,0.06);border-color:rgba(255,165,0,0.3);}
.tn-failing{background:rgba(255,26,26,0.08);border-color:rgba(255,26,26,0.3);}
.tn-unknown{background:rgba(255,26,26,0.02);border-color:rgba(255,26,26,0.08);opacity:0.5;}
.tn-num{font-size:13px;font-weight:700;line-height:1;margin-bottom:1px;}
.tn-healthy .tn-num{color:var(--green);}
.tn-slow    .tn-num{color:orange;}
.tn-failing .tn-num{color:var(--red);}
.tn-unknown .tn-num{color:var(--muted);}
.tn-lbl{font-size:7px;color:var(--muted);text-align:center;
  overflow:hidden;width:100%;text-overflow:ellipsis;white-space:nowrap;}
/* Pulse animation for active nodes */
@keyframes node-pulse{0%,100%{box-shadow:0 0 0 0 rgba(0,255,65,0)}
  50%{box-shadow:0 0 8px 2px rgba(0,255,65,0.2)}}
.tn-healthy{animation:node-pulse 3s infinite;}
@keyframes node-warn{0%,100%{box-shadow:0 0 0 0 rgba(255,165,0,0)}
  50%{box-shadow:0 0 8px 2px rgba(255,165,0,0.2)}}
.tn-slow{animation:node-warn 2s infinite;}

/* TWIN LEGEND */
.twin-legend{display:flex;gap:12px;margin-top:8px;flex-wrap:wrap;}
.tl{display:flex;align-items:center;gap:5px;
  font-family:'Share Tech Mono',monospace;font-size:9px;}
.tld{width:8px;height:8px;border-radius:1px;}
.tl-h{background:var(--green);}
.tl-s{background:orange;}
.tl-f{background:var(--red);}
.tl-u{background:var(--muted);}

/* NODE LEADERBOARD */
.lb-item{display:flex;align-items:center;gap:8px;
  padding:6px 8px;border-bottom:1px solid rgba(68,0,0,0.5);
  font-family:'Share Tech Mono',monospace;font-size:10px;}
.lb-item:last-child{border-bottom:none;}
.lb-rank{width:22px;text-align:center;font-size:14px;}
.lb-name{flex:1;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.lb-lat{color:var(--muted);min-width:42px;text-align:right;}
.lb-bar{width:70px;background:var(--border);height:3px;flex-shrink:0;}
.lb-barf{height:100%;background:linear-gradient(90deg,var(--red3),var(--crimson));}
.lb-rate{min-width:36px;text-align:right;}
.lb-ok{color:var(--green);}
.lb-bd{color:var(--red);}

/* CLUSTER NODES */
.cnodes{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;}
.cn{padding:4px 6px;border:1px solid var(--brd2);background:var(--bg3);
  display:flex;align-items:center;gap:5px;
  font-family:'Share Tech Mono',monospace;font-size:9px;}
.cn-on{border-left:2px solid var(--green);}
.cn-sl{border-left:2px solid orange;}
.cn-off{border-left:2px solid var(--red);opacity:0.5;}
.cnd{width:5px;height:5px;border-radius:50%;flex-shrink:0;}
.cdn{background:var(--green);box-shadow:0 0 4px var(--green);animation:blink 2s infinite;}
.cds{background:orange;}
.cdf{background:var(--red);}
.cnn{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text);}
.cnr{font-size:8px;color:var(--muted);}

/* FAILURE PREDICTION */
.risk-item{padding:7px 9px;border:1px solid var(--brd2);
  background:rgba(255,26,26,0.03);margin-bottom:5px;}
.risk-item:last-child{margin-bottom:0;}
.risk-hdr{display:flex;justify-content:space-between;align-items:center;
  margin-bottom:4px;}
.risk-name{font-family:'Share Tech Mono',monospace;font-size:10px;
  color:var(--text);font-weight:700;}
.risk-pct{font-family:'Orbitron',monospace;font-size:12px;font-weight:700;}
.risk-hi{color:var(--red);text-shadow:0 0 8px rgba(255,26,26,0.6);}
.risk-md{color:orange;}
.risk-reasons{font-family:'Share Tech Mono',monospace;font-size:9px;
  color:var(--muted);display:flex;gap:6px;flex-wrap:wrap;}
.risk-tag{background:rgba(255,26,26,0.08);border:1px solid var(--brd2);
  padding:1px 5px;font-size:8px;}
.risk-bar-outer{background:var(--border);height:3px;margin-top:5px;}
.risk-bar-inner{height:100%;background:linear-gradient(90deg,var(--red3),var(--red));
  transition:width 0.5s;}

/* AI ANALYTICS */
.aig{display:grid;grid-template-columns:1fr 1fr;gap:6px;}
.ait{background:var(--bg3);border:1px solid var(--brd2);padding:7px 9px;}
.ail{font-family:'Share Tech Mono',monospace;font-size:8px;
  letter-spacing:1px;color:var(--muted);text-transform:uppercase;margin-bottom:3px;}
.aiv{font-family:'Orbitron',monospace;font-size:14px;font-weight:700;
  color:var(--red);text-shadow:0 0 8px rgba(255,26,26,0.4);}
.ais{font-size:9px;color:var(--muted);font-family:'Share Tech Mono',monospace;}

/* CLUSTER COMPARE */
.cc-wrap{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.cc-box{background:var(--bg3);border:1px solid var(--brd2);padding:10px;}
.cc-title{font-family:'Rajdhani',sans-serif;font-weight:700;font-size:12px;
  letter-spacing:2px;color:var(--red);margin-bottom:8px;text-transform:uppercase;}
.cc-stat{display:flex;justify-content:space-between;
  font-family:'Share Tech Mono',monospace;font-size:10px;
  padding:3px 0;border-bottom:1px solid rgba(68,0,0,0.3);}
.cc-stat:last-child{border-bottom:none;}
.cc-val{color:var(--red);font-weight:700;}

/* SECURITY */
.sr{display:flex;flex-direction:column;gap:5px;}
.si{display:flex;justify-content:space-between;align-items:center;
  padding:5px 7px;background:var(--bg3);border:1px solid var(--brd2);}
.sl{font-family:'Share Tech Mono',monospace;font-size:9px;color:var(--text);}
.sok{color:var(--green);font-family:'Share Tech Mono',monospace;font-size:9px;font-weight:700;}
.swn{color:orange;font-family:'Share Tech Mono',monospace;font-size:9px;font-weight:700;}
.sbd{color:var(--red);font-family:'Share Tech Mono',monospace;font-size:9px;font-weight:700;}

/* LIVE ALERTS */
.alert-feed{display:flex;flex-direction:column;gap:4px;max-height:220px;overflow-y:auto;}
.alert-feed::-webkit-scrollbar{width:2px;}
.alert-feed::-webkit-scrollbar-thumb{background:var(--brd2);}
.al{display:flex;align-items:flex-start;gap:8px;
  padding:5px 8px;border-left:2px solid;
  font-family:'Share Tech Mono',monospace;font-size:9px;
  animation:al-in 0.3s ease;}
@keyframes al-in{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}
.al-info{border-color:var(--cyan);background:rgba(0,229,255,0.04);}
.al-success{border-color:var(--green);background:rgba(0,255,65,0.04);}
.al-danger{border-color:var(--red);background:rgba(255,26,26,0.06);}
.al-warn{border-color:orange;background:rgba(255,165,0,0.04);}
.al-time{color:var(--muted);flex-shrink:0;font-size:8px;margin-top:1px;}
.al-msg-info{color:var(--cyan);}
.al-msg-success{color:var(--green);}
.al-msg-danger{color:var(--red);}
.al-msg-warn{color:orange;}

/* SUBMIT */
.flbl{font-family:'Share Tech Mono',monospace;font-size:9px;
  letter-spacing:1.5px;color:var(--muted);text-transform:uppercase;
  margin-bottom:3px;display:block;}
.fsel,.finp{background:var(--bg);border:1px solid var(--brd2);
  color:var(--red);font-family:'Share Tech Mono',monospace;font-size:12px;
  padding:7px 9px;width:100%;outline:none;transition:border-color 0.2s;
  -webkit-appearance:none;}
.fsel:focus,.finp:focus{border-color:var(--red);box-shadow:inset 0 0 6px rgba(255,26,26,0.1);}
.finp::placeholder{color:var(--muted);}
.dbtn{background:linear-gradient(135deg,#1a0000,#0d0000);
  border:1px solid var(--red);color:var(--red);
  font-family:'Orbitron',monospace;font-weight:700;font-size:11px;
  letter-spacing:2px;padding:8px 16px;cursor:pointer;
  transition:all 0.2s;text-shadow:var(--glow);
  display:flex;align-items:center;gap:6px;width:100%;
  justify-content:center;margin-top:5px;}
.dbtn:hover{background:rgba(255,26,26,0.1);box-shadow:var(--glow);}
.dbtn:disabled{opacity:0.4;cursor:not-allowed;}

/* RESULT */
.rbox{border:1px solid var(--red3);background:rgba(255,26,26,0.03);padding:10px;}
.rbxh{font-family:'Share Tech Mono',monospace;font-size:8px;
  letter-spacing:2px;color:var(--muted);margin-bottom:5px;}
.rbxv{font-family:'Orbitron',monospace;font-size:26px;font-weight:700;
  color:var(--red);text-shadow:0 0 20px rgba(255,26,26,0.6);margin-bottom:4px;}
.rbxm{font-family:'Share Tech Mono',monospace;font-size:9px;
  color:var(--muted);letter-spacing:1px;}

/* QUEUE */
.qbs{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:7px;}
.qb{font-family:'Share Tech Mono',monospace;font-size:9px;
  letter-spacing:1px;padding:2px 7px;border:1px solid;}
.qbq{color:var(--amber);border-color:var(--red3);background:rgba(255,102,0,0.06);}
.qbr{color:var(--cyan);border-color:#004466;background:rgba(0,229,255,0.06);}
.qbd{color:var(--green);border-color:#003311;background:rgba(0,255,65,0.06);}
.qbf{color:var(--red);border-color:var(--red3);background:rgba(255,26,26,0.06);}

/* TABLE */
.gt{width:100%;border-collapse:collapse;
  font-family:'Share Tech Mono',monospace;font-size:10px;}
.gt th{text-align:left;padding:5px 7px;font-size:8px;letter-spacing:2px;
  text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--brd2);
  font-family:'Rajdhani',sans-serif;font-weight:700;}
.gt td{padding:6px 7px;border-bottom:1px solid rgba(68,0,0,0.35);
  color:var(--text);vertical-align:middle;}
.gt tr:last-child td{border-bottom:none;}
.gt tr:hover td{background:rgba(255,26,26,0.02);}
.b2{display:inline-flex;align-items:center;gap:3px;font-size:9px;
  letter-spacing:1px;font-family:'Rajdhani',sans-serif;font-weight:700;}
.b2ok{color:var(--green);}
.b2f{color:var(--red);}
.b2q{color:var(--amber);}
.b2r{color:var(--cyan);}
.sd{width:5px;height:5px;border-radius:50%;}
.sdok{background:var(--green);box-shadow:0 0 4px var(--green);}
.sdf{background:var(--red);box-shadow:0 0 4px var(--red);}
.sdq{background:var(--amber);}
.sdr{background:var(--cyan);}

/* CHAT */
.cmsgs{max-height:180px;overflow-y:auto;margin-bottom:7px;
  display:flex;flex-direction:column;gap:5px;}
.cmsgs::-webkit-scrollbar{width:2px;}
.cmsgs::-webkit-scrollbar-thumb{background:var(--brd2);}
.mu{align-self:flex-end;background:rgba(255,26,26,0.07);
  border:1px solid var(--red3);padding:4px 8px;
  font-family:'Share Tech Mono',monospace;font-size:9px;
  color:var(--red);max-width:85%;}
.ma{align-self:flex-start;background:rgba(0,229,255,0.04);
  border:1px solid rgba(0,229,255,0.15);padding:5px 8px;
  font-family:'Share Tech Mono',monospace;font-size:9px;
  color:var(--cyan);max-width:90%;line-height:1.5;}
.cir{display:flex;gap:5px;}
.cinp{flex:1;background:var(--bg);border:1px solid var(--brd2);
  color:var(--red);font-family:'Share Tech Mono',monospace;
  font-size:10px;padding:6px 9px;outline:none;}
.cinp:focus{border-color:var(--red3);}
.cinp::placeholder{color:var(--muted);}
.cbtn{background:transparent;border:1px solid var(--red3);
  color:var(--red);font-family:'Orbitron',monospace;font-size:9px;
  padding:6px 12px;cursor:pointer;transition:all 0.15s;letter-spacing:1px;}
.cbtn:hover{background:rgba(255,26,26,0.1);}

/* CSV */
.drop-zone{border:2px dashed var(--red3);padding:18px;text-align:center;
  cursor:pointer;transition:all 0.2s;background:rgba(255,26,26,0.02);}
.drop-zone:hover,.drop-zone.drag{border-color:var(--red);
  background:rgba(255,26,26,0.07);}
.drop-zone p{font-family:'Share Tech Mono',monospace;font-size:10px;color:var(--muted);}
.csv-result{margin-top:8px;display:none;}
.csv-stat{display:flex;justify-content:space-between;padding:4px 7px;
  background:var(--bg3);border:1px solid var(--brd2);
  font-family:'Share Tech Mono',monospace;font-size:9px;margin-bottom:3px;}

/* DB STATS */
.db-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;}
.db-item{background:var(--bg3);border:1px solid var(--brd2);padding:7px 9px;}
.db-lbl{font-family:'Share Tech Mono',monospace;font-size:8px;
  color:var(--muted);margin-bottom:3px;text-transform:uppercase;letter-spacing:1px;}
.db-val{font-family:'Orbitron',monospace;font-size:16px;
  color:var(--red);font-weight:700;}

/* CHART */
.chart-wrap{position:relative;height:130px;}

/* SCROLL */
.scr{max-height:280px;overflow-y:auto;}
.scr::-webkit-scrollbar{width:2px;}
.scr::-webkit-scrollbar-thumb{background:var(--brd2);}

/* SPIN */
.spin{width:10px;height:10px;border:2px solid var(--brd2);
  border-top-color:var(--red);border-radius:50%;display:inline-block;
  animation:sp 0.7s linear infinite;}
@keyframes sp{to{transform:rotate(360deg)}}

/* FOOTER */
footer{border-top:1px solid var(--brd2);padding:7px 14px;
  font-family:'Share Tech Mono',monospace;font-size:9px;letter-spacing:2px;
  color:var(--muted);text-align:center;background:var(--bg2);
  position:relative;z-index:1;}
</style>
</head>
<body>

<header>
  <div class="logo">GRID MASTER</div>
  <div class="v4badge">V4 CYBER OPS</div>
  <div class="pill"><span class="dp"></span>ONLINE</div>
  <div class="pill" id="np">-- NODES</div>
  <div class="pill" id="hp">HEALTH --%</div>
  <div class="hr">
    <div><div class="clock" id="clk">--:--:--</div>
    <div class="lupd" id="lupd">Last Update: --</div></div>
    <button class="rbtn" onclick="ref()">⟳ REFRESH</button>
  </div>
</header>

<main>

<!-- STAT CARDS -->
<div class="s6">
  <div class="sc"><div class="sci">👥</div><div class="scl">Online Nodes</div><div class="scv" id="s-on">--</div><div class="scs" id="s-ons">--/24</div><div class="prog"><div class="progf" id="s-bar" style="width:0%"></div></div></div>
  <div class="sc"><div class="sci">📋</div><div class="scl">Jobs Done</div><div class="scv" id="s-jb">--</div><div class="scs">Total in DB</div></div>
  <div class="sc"><div class="sci">🕐</div><div class="scl">Jobs Queued</div><div class="scv" id="s-qu">--</div><div class="scs">Waiting</div></div>
  <div class="sc"><div class="sci">⚡</div><div class="scl">Tasks/Min</div><div class="scv" id="s-tpm">--</div><div class="scs">Throughput</div></div>
  <div class="sc"><div class="sci">🖥</div><div class="scl">Render Online</div><div class="scv" id="s-rnd">--</div><div class="scs">of 12 nodes</div></div>
  <div class="sc"><div class="sci">🤗</div><div class="scl">HF Online</div><div class="scv" id="s-hf">--</div><div class="scs">of 12 nodes</div></div>
</div>

<!-- SUBMIT + RESULT + ALERTS -->
<div class="g3">
  <div class="panel">
    <div class="ph"><div class="pt">Submit Task</div></div>
    <div class="pb">
      <div style="display:grid;grid-template-columns:150px 1fr;gap:8px;margin-bottom:6px;">
        <div><label class="flbl">Task Type</label>
          <select class="fsel" id="tt">
            <option value="sum">Sum</option>
            <option value="multiply">Multiply</option>
            <option value="average">Average</option>
            <option value="stats">Statistics</option>
          </select></div>
        <div><label class="flbl">Numbers (comma separated)</label>
          <input class="finp" id="tv" placeholder="1,2,3...30 or 10,20,30..."></div>
      </div>
      <button class="dbtn" id="db" onclick="sub()">⚡ DISTRIBUTE</button>
    </div>
  </div>

  <div class="panel">
    <div class="ph"><div class="pt">Result Box</div></div>
    <div class="pb">
      <div id="ri" style="color:var(--muted);font-family:'Share Tech Mono',monospace;font-size:9px;padding:16px 0;text-align:center">Awaiting task submission...</div>
      <div id="rc" style="display:none">
        <div class="rbox">
          <div class="rbxh">COMPUTED RESULT</div>
          <div class="rbxv" id="rv">--</div>
          <div class="rbxm" id="rm"></div>
        </div>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="ph"><div class="pt">Live Alerts</div><div class="pm" id="al-count">0 events</div></div>
    <div class="pb">
      <div class="alert-feed" id="alerts">
        <div class="al al-info"><span class="al-time">--:--</span><span class="al-msg-info">System initializing...</span></div>
      </div>
    </div>
  </div>
</div>

<!-- DIGITAL TWIN + LEADERBOARD -->
<div class="g21">
  <div class="panel">
    <div class="ph"><div class="pt">Digital Twin Network</div><div class="pm">24 nodes — live heatmap</div></div>
    <div class="pb">
      <div class="twin-grid" id="twin"></div>
      <div class="twin-legend">
        <div class="tl"><div class="tld tl-h"></div><span>Healthy (&lt;1s)</span></div>
        <div class="tl"><div class="tld tl-s"></div><span>Slow (1-2s)</span></div>
        <div class="tl"><div class="tld tl-f"></div><span>Failing</span></div>
        <div class="tl"><div class="tld tl-u"></div><span>Unknown</span></div>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="ph"><div class="pt">Node Leaderboard</div><div class="pm">ranked by speed</div></div>
    <div class="pb scr" id="lb">
      <div style="color:var(--muted);text-align:center;padding:20px;font-family:'Share Tech Mono',monospace;font-size:9px"><span class="spin"></span> Loading...</div>
    </div>
  </div>
</div>

<!-- RENDER + HF CLUSTER -->
<div class="g2">
  <div class="panel">
    <div class="ph"><div class="pt">Render Cluster</div><div class="pm" id="rc-m">--/12</div></div>
    <div class="pb"><div class="cnodes" id="rn"></div></div>
  </div>
  <div class="panel">
    <div class="ph"><div class="pt">HuggingFace Cluster</div><div class="pm" id="hc-m">--/12</div></div>
    <div class="pb"><div class="cnodes" id="hn"></div></div>
  </div>
</div>

<!-- AI FAILURE PREDICTION + CLUSTER COMPARE + GRID AI -->
<div class="g3">
  <div class="panel">
    <div class="ph"><div class="pt">AI Failure Predictor</div><div class="pm" id="risk-meta">analyzing...</div></div>
    <div class="pb scr" id="risks">
      <div style="color:var(--muted);text-align:center;padding:16px;font-family:'Share Tech Mono',monospace;font-size:9px"><span class="spin"></span></div>
    </div>
  </div>

  <div class="panel">
    <div class="ph"><div class="pt">Cluster Comparison</div></div>
    <div class="pb">
      <div class="cc-wrap">
        <div class="cc-box">
          <div class="cc-title">🖥 Render</div>
          <div class="cc-stat"><span>Online</span><span class="cc-val" id="cc-ron">--</span></div>
          <div class="cc-stat"><span>Success</span><span class="cc-val" id="cc-rs">--%</span></div>
          <div class="cc-stat"><span>Avg Lat</span><span class="cc-val" id="cc-ra">--s</span></div>
          <div class="cc-stat"><span>Winner</span><span class="cc-val" id="cc-rw">--</span></div>
        </div>
        <div class="cc-box">
          <div class="cc-title">🤗 HuggingFace</div>
          <div class="cc-stat"><span>Online</span><span class="cc-val" id="cc-hon">--</span></div>
          <div class="cc-stat"><span>Success</span><span class="cc-val" id="cc-hs">--%</span></div>
          <div class="cc-stat"><span>Avg Lat</span><span class="cc-val" id="cc-ha">--s</span></div>
          <div class="cc-stat"><span>Winner</span><span class="cc-val" id="cc-hw">--</span></div>
        </div>
      </div>
      <div style="margin-top:10px;" class="aig">
        <div class="ait"><div class="ail">Total Ops</div><div class="aiv" id="ai-ops">--</div></div>
        <div class="ait"><div class="ail">Success Rate</div><div class="aiv" id="ai-sr">--%</div></div>
        <div class="ait"><div class="ail">Avg Response</div><div class="aiv" id="ai-avg">--</div><div class="ais">seconds</div></div>
        <div class="ait"><div class="ail">Pred. Failures</div><div class="aiv" id="ai-pf">--</div></div>
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="ph"><div class="pt">Grid AI</div><div class="pm">v4 enhanced</div></div>
    <div class="pb">
      <div class="cmsgs" id="cm">
        <div class="ma">⚡ GRID AI v4 ONLINE<br>Try: predict failures, compare clusters, leaderboard...</div>
      </div>
      <div class="cir">
        <input class="cinp" id="ci" placeholder="predict failures..." onkeydown="if(event.key==='Enter')ask()">
        <button class="cbtn" onclick="ask()">ASK</button>
      </div>
    </div>
  </div>
</div>

<!-- HISTORY CHART + CSV + SECURITY + DB -->
<div class="g2" style="margin-bottom:8px;">
  <div class="panel">
    <div class="ph"><div class="pt">Historical Latency</div><div class="pm">last 20 job averages</div></div>
    <div class="pb"><div class="chart-wrap"><canvas id="lchart"></canvas></div></div>
  </div>
  <div class="panel">
    <div class="ph"><div class="pt">CSV Analysis</div><div class="pm">drag & drop</div></div>
    <div class="pb">
      <div class="drop-zone" id="dz" onclick="document.getElementById('cf').click()" ondragover="dzev(event)" ondrop="dpev(event)">
        <p>📂 DROP CSV FILE HERE</p>
        <p style="margin-top:4px;font-size:8px">click to browse</p>
      </div>
      <input type="file" id="cf" accept=".csv" style="display:none" onchange="uploadCSV(this)">
      <div class="csv-result" id="cr">
        <div class="csv-stat"><span>Rows</span><span id="csv-rows" style="color:var(--red)">--</span></div>
        <div class="csv-stat"><span>Values</span><span id="csv-vals" style="color:var(--red)">--</span></div>
        <div class="csv-stat"><span>Sum</span><span id="csv-sum" style="color:var(--red)">--</span></div>
        <div class="csv-stat"><span>Average</span><span id="csv-avg" style="color:var(--red)">--</span></div>
        <div class="csv-stat"><span>Min / Max</span><span id="csv-mm" style="color:var(--red)">--</span></div>
        <div class="csv-stat"><span>Time</span><span id="csv-t" style="color:var(--red)">--</span></div>
      </div>
    </div>
  </div>
</div>

<div class="g2" style="margin-bottom:8px;">
  <div class="panel">
    <div class="ph"><div class="pt">Security Center</div></div>
    <div class="pb"><div class="sr">
      <div class="si"><span class="sl">API Key</span><span class="sok" id="sec-k">ACTIVE</span></div>
      <div class="si"><span class="sl">Unauthorized Requests</span><span id="sec-u" class="sok">0</span></div>
      <div class="si"><span class="sl">Total Requests</span><span class="sok" id="sec-r">0</span></div>
      <div class="si"><span class="sl">Attack Attempts</span><span id="sec-a" class="sok">0</span></div>
      <div class="si"><span class="sl">Node Integrity</span><span class="sok">PASS</span></div>
      <div class="si"><span class="sl">Grid Health</span><span class="sok" id="sec-h">--%</span></div>
    </div></div>
  </div>
  <div class="panel">
    <div class="ph"><div class="pt">Storage Stats</div></div>
    <div class="pb">
      <div class="db-grid">
        <div class="db-item"><div class="db-lbl">Total Records</div><div class="db-val" id="db-rec">--</div></div>
        <div class="db-item"><div class="db-lbl">DB Size (KB)</div><div class="db-val" id="db-sz">--</div></div>
        <div class="db-item"><div class="db-lbl">Queued Jobs</div><div class="db-val" id="db-qu">--</div></div>
        <div class="db-item"><div class="db-lbl">Success Rate</div><div class="db-val" id="db-sr">--%</div></div>
      </div>
    </div>
  </div>
</div>

<!-- QUEUE + RECENT JOBS -->
<div class="g2">
  <div class="panel">
    <div class="ph"><div class="pt">Job Queue</div><div class="pm" id="qt"></div></div>
    <div class="pb">
      <div class="qbs" id="qb"></div>
      <div class="scr" id="qbody"></div>
    </div>
  </div>
  <div class="panel">
    <div class="ph"><div class="pt">Recent Jobs</div><div class="pm">Last 20</div></div>
    <div class="pb"><div class="scr"><table class="gt">
      <thead><tr><th>Job ID</th><th>Time</th><th>Task</th><th>Node</th><th>Status</th><th>Time</th><th>Result</th></tr></thead>
      <tbody id="jb"><tr><td colspan="7" style="text-align:center;padding:16px;color:var(--muted)"><span class="spin"></span></td></tr></tbody>
    </table></div></div>
  </div>
</div>

</main>
<footer>GRID MASTER V4 — CYBER OPERATIONS CENTER &nbsp;|&nbsp; DARK RED LIGHTNING EDITION &nbsp;|&nbsp; DHONI GRID SYSTEMS &nbsp;|&nbsp; <span id="ft"></span></footer>

<script>
const RN=["grid-nodes","grid-nodes2","grid-nodes3","grid-nodes4","grid-nodesv2","grid-nodesv2-1","grid-nodesr2-7","grid-nodesr8","grid-nodes9","grid-nodes10","grid-nodes11","grid-nodes12"];
const HN=["bug-spy1-grid222","dhoni22-girdtest","done1237-gridc","dhonims-grid333","bug-spy1-gridnodehf5","bug-spy1-gridnodehf6","dhoni22-gridnodehf7","dhoni22-gridnodehf8","done1237-gridnodehf9","done1237-gridnodehf10","dhonims-gridnodehf11","dhonims-grid12"];
const AN=[...RN,...HN];

function tick(){
  const n=new Date();
  document.getElementById('clk').textContent=n.toTimeString().slice(0,8);
  document.getElementById('ft').textContent=n.toLocaleDateString()+' '+n.toTimeString().slice(0,8);
}
setInterval(tick,1000);tick();

async function fj(u){try{const r=await fetch(u);return await r.json();}catch{return null;}}

// CHART
const ctx=document.getElementById('lchart').getContext('2d');
const lChart=new Chart(ctx,{type:'line',data:{
  labels:[],
  datasets:[{
    label:'Avg Latency (s)',
    data:[],
    borderColor:'#cc0000',
    backgroundColor:'rgba(204,0,0,0.08)',
    tension:0.4,pointRadius:3,
    pointBackgroundColor:'#ff1a1a',
    borderWidth:1.5
  }]
},{
  responsive:true,maintainAspectRatio:false,
  plugins:{legend:{labels:{color:'#883333',font:{family:'Share Tech Mono',size:9},boxWidth:10}}},
  scales:{
    x:{ticks:{color:'#883333',font:{size:8}},grid:{color:'rgba(68,0,0,0.4)'},border:{color:'#4d0000'}},
    y:{ticks:{color:'#883333',font:{size:8}},grid:{color:'rgba(68,0,0,0.4)'},border:{color:'#4d0000'},beginAtZero:true}
  },
  animation:{duration:400}
}});

function rStats(s,sec,db){
  document.getElementById('s-on').textContent=s.online;
  document.getElementById('s-ons').textContent=s.online+'/'+s.total+' · '+s.health+'%';
  document.getElementById('s-bar').style.width=s.health+'%';
  document.getElementById('s-jb').textContent=(s.jobs||0).toLocaleString();
  document.getElementById('s-qu').textContent=s.queued||0;
  document.getElementById('s-tpm').textContent=s.tpm||0;
  document.getElementById('s-rnd').textContent=s.render_on||0;
  document.getElementById('s-hf').textContent=s.hf_on||0;
  document.getElementById('np').textContent=s.online+' NODES ONLINE';
  document.getElementById('hp').textContent='HEALTH '+s.health+'%';
  document.getElementById('sec-h').textContent=s.health+'%';
  document.getElementById('lupd').textContent='Last Update: Just now';
  if(sec){
    const u=sec.unauthorized||0;
    document.getElementById('sec-u').textContent=u;
    document.getElementById('sec-u').className=u>0?'sbd':'sok';
    document.getElementById('sec-r').textContent=sec.requests||0;
    document.getElementById('sec-a').textContent=sec.attacks||0;
  }
  if(db){
    document.getElementById('db-rec').textContent=(db.records||0).toLocaleString();
    document.getElementById('db-sz').textContent=db.size_kb||0;
    document.getElementById('db-qu').textContent=s.queued||0;
    document.getElementById('db-sr').textContent=s.health+'%';
  }
}

function rTwin(nd){
  const el=document.getElementById('twin');
  el.innerHTML=AN.map((n,i)=>{
    const suf=i<12?'.onrender.com':'.hf.space';
    const url='https://'+n+suf;
    const d=nd[url]||{};
    const col=d.color||'unknown';
    const num=String(i+1).padStart(2,'0');
    const lbl=n.replace('grid-','').replace('nodes','n').slice(0,5);
    const tip=n+'\n'+( d.avg?d.avg+'s ':'' )+(d.rate?d.rate+'%':'');
    return `<div class="twin-node tn-${col}" title="${tip}"><div class="tn-num">${num}</div><div class="tn-lbl">${lbl}</div></div>`;
  }).join('');
}

function rLeaderboard(lb){
  const el=document.getElementById('lb');
  if(!lb||!lb.length){
    el.innerHTML='<div style="color:var(--muted);text-align:center;padding:16px;font-family:Share Tech Mono,monospace;font-size:9px">No data yet — run some tasks first</div>';
    return;
  }
  const medals=['🥇','🥈','🥉','4.','5.','6.','7.','8.'];
  el.innerHTML=lb.map((r,i)=>{
    const ok=r.rate>=70;
    return `<div class="lb-item">
      <div class="lb-rank">${medals[i]||i+1}</div>
      <div class="lb-name">${r.name}</div>
      <div class="lb-lat">${r.avg}s</div>
      <div class="lb-bar"><div class="lb-barf" style="width:${Math.min(100,100-Math.min(r.avg*30,95))}%"></div></div>
      <div class="lb-rate ${ok?'lb-ok':'lb-bd'}">${r.rate}%</div>
    </div>`;
  }).join('');
}

function rCluster(nd,names,suf,elId,metaId){
  const el=document.getElementById(elId);
  const meta=document.getElementById(metaId);
  let on=0;
  el.innerHTML=names.map(n=>{
    const url='https://'+n+suf;
    const d=nd[url]||{};
    const col=d.color||'unknown';
    const ok=col==='healthy';const sl=col==='slow';
    if(ok||sl)on++;
    const cls=ok?'cn-on':sl?'cn-sl':'cn-off';
    const dcls=ok?'cdn':sl?'cds':'cdf';
    const short=n.replace('grid-','').replace('nodesv','v').replace('nodesr','r').slice(0,12);
    return `<div class="cn ${cls}"><div class="cnd ${dcls}"></div><div class="cnn">${short}</div><div class="cnr">${(ok||sl)?(d.rate||0)+'%':'OFF'}</div></div>`;
  }).join('');
  meta.textContent=on+'/'+names.length+' online';
}

function rRisks(risks){
  const el=document.getElementById('risks');
  const meta=document.getElementById('risk-meta');
  if(!risks||!risks.length){
    el.innerHTML='<div style="color:var(--green);text-align:center;padding:16px;font-family:Share Tech Mono,monospace;font-size:9px">✅ No nodes at risk</div>';
    meta.textContent='all clear';
    return;
  }
  meta.textContent=risks.length+' at risk';
  el.innerHTML=risks.map(r=>{
    const cls=r.risk>=70?'risk-hi':'risk-md';
    return `<div class="risk-item">
      <div class="risk-hdr">
        <div class="risk-name">⚠ ${r.name}</div>
        <div class="risk-pct ${cls}">${r.risk}%</div>
      </div>
      <div class="risk-reasons">${r.reasons.map(x=>`<span class="risk-tag">${x}</span>`).join('')}</div>
      <div class="risk-bar-outer"><div class="risk-bar-inner" style="width:${r.risk}%"></div></div>
    </div>`;
  }).join('');
}

function rCompare(ai,s){
  document.getElementById('cc-ron').textContent=s.render_on+'/12';
  document.getElementById('cc-rs').textContent=(ai.render_success||0)+'%';
  document.getElementById('cc-ra').textContent=(ai.render_avg||0)+'s';
  const renderWins=ai.render_avg&&ai.hf_avg&&ai.render_avg<ai.hf_avg;
  document.getElementById('cc-rw').textContent=renderWins?'🏆 FASTER':'--';
  document.getElementById('cc-hon').textContent=s.hf_on+'/12';
  document.getElementById('cc-hs').textContent=(ai.hf_success||0)+'%';
  document.getElementById('cc-ha').textContent=(ai.hf_avg||0)+'s';
  document.getElementById('cc-hw').textContent=(!renderWins&&ai.hf_avg)?'🏆 FASTER':'--';
  document.getElementById('ai-ops').textContent=(ai.total_ops||0).toLocaleString();
  document.getElementById('ai-sr').textContent=(ai.success_rate||0)+'%';
  document.getElementById('ai-avg').textContent=ai.avg_response||'--';
  const pf=ai.predicted_failures||0;
  const pfel=document.getElementById('ai-pf');
  pfel.textContent=pf;
  pfel.style.color=pf>0?'var(--red)':'var(--green)';
}

function rAlerts(alts){
  const el=document.getElementById('alerts');
  document.getElementById('al-count').textContent=(alts.length)+' events';
  if(!alts.length){
    el.innerHTML='<div class="al al-info"><span class="al-time">--:--</span><span class="al-msg-info">No alerts yet</span></div>';
    return;
  }
  const cls={info:'al-info',success:'al-success',danger:'al-danger',warn:'al-warn'};
  const mcls={info:'al-msg-info',success:'al-msg-success',danger:'al-msg-danger',warn:'al-msg-warn'};
  el.innerHTML=alts.map(a=>`<div class="al ${cls[a.level]||'al-info'}"><span class="al-time">${a.time}</span><span class="${mcls[a.level]||'al-msg-info'}">${a.msg}</span></div>`).join('');
}

function rQueue(qs,qlist){
  const cls={queued:'qbq',running:'qbr',completed:'qbd',failed:'qbf'};
  const total=Object.values(qs).reduce((a,b)=>a+b,0);
  document.getElementById('qt').textContent='Total: '+total;
  document.getElementById('qb').innerHTML=Object.entries(qs).map(([s,c])=>`<div class="qb ${cls[s]||'qbq'}">${c} ${s.toUpperCase()}</div>`).join('')||'<div style="color:var(--muted);font-size:9px">Empty</div>';
  const body=document.getElementById('qbody');
  if(!qlist||!qlist.length){body.innerHTML='<div style="color:var(--muted);font-size:9px;padding:8px;text-align:center">No jobs</div>';return;}
  body.innerHTML=`<table class="gt"><thead><tr><th>ID</th><th>Task</th><th>Status</th><th>Pri</th><th>Retries</th></tr></thead><tbody>${
    qlist.slice(0,8).map(j=>{
      const sc=j.status==='completed'?'sdok':j.status==='failed'?'sdf':j.status==='running'?'sdr':'sdq';
      const tc=j.status==='completed'?'b2ok':j.status==='failed'?'b2f':j.status==='running'?'b2r':'b2q';
      const pri=j.priority===1?'🔴':j.priority===3?'⚪':'🟡';
      return `<tr><td style="color:var(--red)">${(j.job_id||'').slice(0,7)}</td><td>${(j.task||'').toUpperCase()}</td><td><span class="b2 ${tc}"><span class="sd ${sc}"></span>${(j.status||'').toUpperCase()}</span></td><td>${pri}</td><td>${j.retries||0}</td></tr>`;
    }).join('')
  }</tbody></table>`;
}

function rJobs(jobs){
  const tbody=document.getElementById('jb');
  if(!jobs||!jobs.length){tbody.innerHTML='<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:14px">No jobs yet</td></tr>';return;}
  tbody.innerHTML=jobs.map(j=>{
    const ok=j.status==='completed';
    const node=(j.node||'').replace('https://','').split('.')[0].slice(0,18);
    return `<tr>
      <td style="color:var(--red)">${(j.job_id||'').slice(0,7)}</td>
      <td style="color:var(--muted)">${(j.timestamp||'').slice(11,19)}</td>
      <td>${(j.task||'').toUpperCase()}</td>
      <td style="color:var(--muted)">${node}</td>
      <td><span class="b2 ${ok?'b2ok':'b2f'}"><span class="sd ${ok?'sdok':'sdf'}"></span>${(j.status||'').toUpperCase()}</span></td>
      <td>${j.elapsed?j.elapsed.toFixed(2)+'s':'--'}</td>
      <td style="color:var(--red)">${(j.result||'').slice(0,18)}</td>
    </tr>`;
  }).join('');
}

function rHistory(h){
  if(!h||!h.labels||!h.labels.length)return;
  lChart.data.labels=h.labels;
  lChart.data.datasets[0].data=h.render;
  lChart.update();
}

async function ref(){
  const d=await fj('/api/dashboard');
  if(!d)return;
  window._nd=d.nodes||{};
  rStats(d.stats,d.security,d.db);
  rTwin(d.nodes);
  rLeaderboard(d.ai.leaderboard);
  rCluster(d.nodes,RN,'.onrender.com','rn','rc-m');
  rCluster(d.nodes,HN,'.hf.space','hn','hc-m');
  rRisks(d.ai.failure_risks);
  rCompare(d.ai,d.stats);
  rAlerts(d.alerts||[]);
  rQueue(d.queue||{},d.queue_list||[]);
  rJobs(d.jobs||[]);
  rHistory(d.history);
}

async function sub(){
  const task=document.getElementById('tt').value;
  const raw=document.getElementById('tv').value;
  const values=raw.split(',').map(x=>parseFloat(x.trim())).filter(x=>!isNaN(x));
  if(!values.length){alert('Enter valid numbers!');return;}
  const btn=document.getElementById('db');
  btn.textContent='⏳ PROCESSING...';btn.disabled=true;
  document.getElementById('ri').style.display='none';
  document.getElementById('rc').style.display='none';
  try{
    const r=await fetch('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task,values})});
    const d=await r.json();
    document.getElementById('rc').style.display='block';
    if(d.error){
      document.getElementById('rv').textContent='ERR: '+d.error;
      document.getElementById('rm').textContent='';
    }else{
      document.getElementById('rv').textContent=d.result;
      document.getElementById('rm').textContent='JOB: '+d.job_id+' | '+d.completed+'/'+d.total+' NODES | '+d.elapsed+'s';
    }
    ref();
  }catch(e){alert('Error: '+e.message);}
  finally{btn.textContent='⚡ DISTRIBUTE';btn.disabled=false;}
}

async function ask(){
  const inp=document.getElementById('ci');
  const q=inp.value.trim();if(!q)return;
  inp.value='';
  const msgs=document.getElementById('cm');
  msgs.innerHTML+=`<div class="mu">${q}</div><div class="ma"><span class="spin"></span></div>`;
  msgs.scrollTop=msgs.scrollHeight;
  try{
    const r=await fetch('/api/ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q})});
    const d=await r.json();
    const all=msgs.querySelectorAll('.ma');
    all[all.length-1].innerHTML=d.response||'No response.';
  }catch(e){
    const all=msgs.querySelectorAll('.ma');
    all[all.length-1].textContent='Error: '+e.message;
  }
  msgs.scrollTop=msgs.scrollHeight;
}

function dzev(e){e.preventDefault();document.getElementById('dz').classList.add('drag');}
function dpev(e){e.preventDefault();document.getElementById('dz').classList.remove('drag');const f=e.dataTransfer.files[0];if(f)processCSV(f);}
function uploadCSV(inp){if(inp.files[0])processCSV(inp.files[0]);}
async function processCSV(file){
  const fd=new FormData();fd.append('file',file);
  document.getElementById('cr').style.display='block';
  document.getElementById('csv-rows').textContent='⏳';
  try{
    const r=await fetch('/api/csv',{method:'POST',body:fd});
    const d=await r.json();
    if(d.error){document.getElementById('csv-rows').textContent='ERR: '+d.error;return;}
    document.getElementById('csv-rows').textContent=d.rows;
    document.getElementById('csv-vals').textContent=(d.values||0).toLocaleString();
    document.getElementById('csv-sum').textContent=d.stats?(d.stats.sum||0).toFixed(2):'--';
    document.getElementById('csv-avg').textContent=d.stats?(d.stats.avg||0).toFixed(4):'--';
    document.getElementById('csv-mm').textContent=d.stats?(d.stats.min||0).toFixed(2)+' / '+(d.stats.max||0).toFixed(2):'--';
    document.getElementById('csv-t').textContent=d.elapsed+'s';
    ref();
  }catch(e){document.getElementById('csv-rows').textContent='Error';}
}

ref();
setInterval(ref,30000);
</script>
</body>
</html>'''

if __name__ == '__main__':
    port = int(os.environ.get("DASHBOARD_PORT", 5000))
    print(f"\n⚡ Grid Master Dashboard V4 — CYBER OPS CENTER")
    print(f"   Theme  : Dark Red Lightning")
    print(f"   Open   : http://localhost:{port}")
    print(f"   Features: Digital Twin, Leaderboard, AI Predictor,")
    print(f"             Historical Chart, Cluster Compare, Live Alerts")
    app.run(host='0.0.0.0', port=port, debug=False)
