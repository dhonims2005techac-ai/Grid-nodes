from flask import Flask, request, jsonify
import time
import os

app = Flask(__name__)
API_KEY = os.environ.get("GRID_API_KEY")

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "node": os.environ.get("NODE_NAME", "grid-node"),
        "message": "Grid node is running!"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/compute', methods=['POST'])
def compute():
    data = request.json
    task = data.get('task', '')
    values = data.get('values', [])

    # This is where the node does its computation
    if task == 'sum':
        result = sum(values)
    elif task == 'multiply':
        result = 1
        for v in values:
            result *= v
    elif task == 'average':
        result = sum(values) / len(values) if values else 0
    else:
        result = f"Unknown task: {task}"

    return jsonify({
        "node": os.environ.get("NODE_NAME", "grid-node"),
        "task": task,
        "result": result,
        "status": "completed"
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT",7860 ))
    print(f"Grid node starting on port {port}...")
    app.run(host='0.0.0.0', port=port)
