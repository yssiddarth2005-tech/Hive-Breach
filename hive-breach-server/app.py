import os, sqlite3, uuid, json
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "saves.db")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS saves (token TEXT PRIMARY KEY, data TEXT NOT NULL)")
    return conn

DEFAULT_SAVE = {
    "opts": {"music": True, "sfx": True, "shake": True, "diff": 1},
    "best": 0,
    "codex": [],
    "skins": [],
    "skin": "standard",
    "chapters": 0,
}

@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return ("", 204)

@app.route("/api/new", methods=["POST"])
def new_token():
    token = uuid.uuid4().hex
    conn = db()
    conn.execute("INSERT INTO saves (token, data) VALUES (?, ?)", (token, json.dumps(DEFAULT_SAVE)))
    conn.commit()
    conn.close()
    return jsonify({"token": token, "data": DEFAULT_SAVE})

@app.route("/api/save/<token>", methods=["GET"])
def load_save(token):
    conn = db()
    row = conn.execute("SELECT data FROM saves WHERE token=?", (token,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "unknown token"}), 404
    return jsonify({"token": token, "data": json.loads(row[0])})

@app.route("/api/save/<token>", methods=["POST"])
def save_save(token):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "bad payload"}), 400
    conn = db()
    row = conn.execute("SELECT data FROM saves WHERE token=?", (token,)).fetchone()
    current = json.loads(row[0]) if row else dict(DEFAULT_SAVE)
    for k, v in payload.items():
        if k in DEFAULT_SAVE:
            current[k] = v
    conn.execute(
        "INSERT INTO saves (token, data) VALUES (?, ?) ON CONFLICT(token) DO UPDATE SET data=excluded.data",
        (token, json.dumps(current)),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
