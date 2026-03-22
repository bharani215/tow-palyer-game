FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD gunicorn --worker-class gthread --threads 4 --bind 0.0.0.0:$PORT server:app
```

Click **Commit changes** ✅

---

### Step 2 — Create `requirements.txt`

Click **Add file → Create new file**

Name:
```
requirements.txt
```

Paste:
```
flask==2.3.3
flask-socketio==5.3.6
simple-websocket==0.10.1
gunicorn==21.2.0
Werkzeug==2.3.7
```

Click **Commit changes** ✅

---

### Step 3 — Make sure these files exist in root:
```
tow-palyer-game/
  ├── server.py        ✅
  ├── requirements.txt ✅
  ├── Dockerfile       ✅ (just added)
  └── templates/
        └── index.html ✅
