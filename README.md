# Grid Node - Setup Instructions

## Files in This Repository
- `Dockerfile` — packages the Python app into a container
- `worker.py` — the node script that receives and processes tasks
- `master.py` — run this from Termux to control all nodes
- `docker-compose.yml` — for local testing

---

## Step 1: Upload This Repo to GitHub
1. Create a new GitHub repository called `grid-node`
2. Upload all these files to it

---

## Step 2: Deploy on Render (4 accounts)
1. Log into each Render account
2. Click "New" → "Web Service"
3. Connect this GitHub repository
4. Set environment: Docker
5. Click Deploy
6. Copy the URL given (e.g. https://grid-node-1.onrender.com)

---

## Step 3: Deploy on Vercel (4 accounts)
1. Log into each Vercel account
2. Click "New Project"
3. Import this GitHub repository
4. Click Deploy
5. Copy the URL given

---

## Step 4: Deploy on Hugging Face (4 accounts)
1. Log into each Hugging Face account
2. Click "New Space"
3. Choose "Docker" as Space SDK
4. Connect this GitHub repository
5. Click Deploy
6. Copy the URL given

---

## Step 5: Update master.py
After getting all 12 URLs, open master.py and replace the placeholder URLs with your real node URLs.

---

## Step 6: Run from Termux
```
pkg install python
pip install requests
python master.py
```

---

## Step 7: Generate SSH Key in Termux
```
ssh-keygen -t ed25519 -f ~/.ssh/id_grid -N ""
cat ~/.ssh/id_grid.pub
```
Copy the output and add it to your GitHub SSH keys under Settings → SSH Keys.
