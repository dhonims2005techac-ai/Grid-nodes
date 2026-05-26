import requests
import json
import concurrent.futures

# ============================================================
# ADD YOUR 12 NODE URLs HERE AFTER DEPLOYING ON EACH PLATFORM
# ============================================================
NODES = [
    # Render nodes (4)
    "https://grid-nodes.onrender.com",
    "https://grid-nodes2.onrender.com",
    "https://grid-nodes3.onrender.com",
    "https://grid-nodes4.onrender.com",
    # Vercel nodes (4)
    "https://grid-nodesv2-81f0nythy-done-s-projects1.vercel.app/",
    "https://your-vercel-node-2.vercel.app",
    "https://your-vercel-node-3.vercel.app",
    "https://your-vercel-node-4.vercel.app",
    # Hugging Face nodes (4)
    "https://bug-spy1-grid222.hf.space",
    "https://dhoni22-girdtest.hf.space",
    "https://done1237-gridc.hf.space",
    "https://dhonims-grid333.hf.space",
]

def check_node(url):
    """Check if a node is online"""
    try:
        response = requests.get(f"{url}/health", timeout=10)
        if response.status_code == 200:
            print(f"✅ Node ONLINE: {url}")
            return True
        else:
            print(f"❌ Node OFFLINE: {url}")
            return False
    except Exception as e:
        print(f"❌ Node OFFLINE: {url} - {str(e)}")
        return False

def send_task(node_url, task, values):
    """Send a computation task to a node"""
    try:
        payload = {"task": task, "values": values}
        response = requests.post(f"{node_url}/compute", json=payload, timeout=30)
        return response.json()
    except Exception as e:
        return {"status": "failed", "error": str(e), "node": node_url}

def distribute_task(task, data_chunks):
    """Distribute work across all online nodes"""
    online_nodes = [n for n in NODES if check_node(n)]
    
    if not online_nodes:
        print("No nodes available!")
        return []

    print(f"\n🚀 Distributing task '{task}' across {len(online_nodes)} nodes...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(online_nodes)) as executor:
        futures = {
            executor.submit(send_task, node, task, chunk): node
            for node, chunk in zip(online_nodes, data_chunks)
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"Result from node: {result}")
    
    return results

def check_all_nodes():
    """Check status of all nodes"""
    print("\n🔍 Checking all nodes...\n")
    online = 0
    for node in NODES:
        if check_node(node):
            online += 1
    print(f"\n📊 Total: {online}/{len(NODES)} nodes online")

if __name__ == '__main__':
    print("=" * 50)
    print("   GRID COMPUTING MASTER CONTROLLER")
    print("=" * 50)
    
    # Step 1: Check all nodes
    check_all_nodes()
    
    # Step 2: Example - distribute a sum task across nodes
    print("\n📤 Sending test computation to grid...")
    data_chunks = [
    list(range(1, 1000)),
    list(range(1000, 2000)),
    list(range(2000, 3000)),
    list(range(3000, 4000)),
    list(range(4000, 5000)),
    list(range(5000, 6000)),
    list(range(6000, 7000)),
    list(range(7000, 8000)),
    ]
    
    results = distribute_task("sum", data_chunks)
    
    print("\n✅ All results collected:")
    for r in results:
        print(r)
