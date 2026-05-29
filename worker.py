from flask import Flask, request, jsonify
import os, math

app = Flask(__name__)
SECRET_KEY = os.environ.get("GRID_SECRET")
NODE_NAME  = os.environ.get("NODE_NAME", "grid-node")

@app.route('/')
def home():
    return jsonify({"status": "online", "node": NODE_NAME, "message": "Grid node is running!"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "node": NODE_NAME})

@app.route('/compute', methods=['POST'])
def compute():
    if request.headers.get("X-API-KEY") != SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data   = request.json
    task   = data.get('task', '')
    values = data.get('values', [])

    if not values:
        return jsonify({"status": "failed", "error": "No values provided"}), 400

    try:
        if task == 'sum':
            result = {"sum": sum(values), "count": len(values)}

        elif task == 'multiply':
            r = 1
            for v in values: r *= v
            result = {"product": r, "count": len(values)}

        elif task == 'average':
            s = sum(values)
            result = {"sum": s, "count": len(values), "local_avg": s / len(values)}

        elif task == 'stats':
            s = sorted(values)
            n = len(s)
            total = sum(s)
            avg   = total / n
            var   = sum((x - avg) ** 2 for x in s) / n
            result = {"sum": total, "count": n, "min": s[0], "max": s[-1],
                      "avg": avg, "std_dev": math.sqrt(var)}

        elif task == 'primes':
            def is_prime(n):
                if n < 2: return False
                for i in range(2, int(math.sqrt(n)) + 1):
                    if n % i == 0: return False
                return True
            primes = [int(x) for x in values if is_prime(int(x))]
            result = {"primes": primes, "count": len(primes)}

        else:
            return jsonify({"status": "failed", "error": f"Unknown task: {task}",
                            "node": NODE_NAME}), 400

        return jsonify({"node": NODE_NAME, "task": task,
                        "status": "completed", "result": result})

    except Exception as e:
        return jsonify({"status": "failed", "error": str(e), "node": NODE_NAME}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))
    print(f"Grid node starting on port {port}...")
    app.run(host='0.0.0.0', port=port)
