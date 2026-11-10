from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from pydantic import ValidationError
from werkzeug.utils import secure_filename

from src.config import ATTACHMENTS_DIR, CONTACTS_PATH, MESSAGE_PATH
from src.contacts import Contact, load_contacts, load_message, save_contacts
from src.main import load_attachments

app = Flask(__name__)

_run_lock = threading.Lock()
_run_state = {"running": False, "lines": [], "returncode": None}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/contacts", methods=["GET"])
def get_contacts():
    if not Path(CONTACTS_PATH).exists():
        return jsonify([])
    contacts = load_contacts(CONTACTS_PATH)
    return jsonify([{"name": c.name, "phone": c.phone} for c in contacts])


@app.route("/api/contacts", methods=["POST"])
def put_contacts():
    rows = request.get_json(force=True)
    contacts = []
    errors = []
    for i, row in enumerate(rows):
        try:
            contacts.append(Contact(name=row.get("name", ""), phone=row.get("phone", "")))
        except ValidationError as exc:
            errors.append({"row": i, "error": str(exc.errors()[0]["msg"])})
    if errors:
        return jsonify({"errors": errors}), 400
    save_contacts(contacts, CONTACTS_PATH)
    return jsonify({"ok": True, "count": len(contacts)})


@app.route("/api/message", methods=["GET"])
def get_message():
    if not Path(MESSAGE_PATH).exists():
        return jsonify({"message": ""})
    return jsonify({"message": Path(MESSAGE_PATH).read_text(encoding="utf-8")})


@app.route("/api/message", methods=["POST"])
def put_message():
    text = request.get_json(force=True).get("message", "")
    Path(MESSAGE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(MESSAGE_PATH).write_text(text, encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/attachments", methods=["GET"])
def get_attachments():
    return jsonify([{"name": p.name, "size": p.stat().st_size} for p in load_attachments()])


@app.route("/api/attachments", methods=["POST"])
def upload_attachments():
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for file in request.files.getlist("files"):
        if not file.filename:
            continue
        filename = secure_filename(file.filename)
        file.save(ATTACHMENTS_DIR / filename)
        saved.append(filename)
    return jsonify({"ok": True, "saved": saved})


@app.route("/data-attachments/<path:filename>", methods=["GET"])
def serve_attachment(filename: str):
    return send_from_directory(Path(ATTACHMENTS_DIR).resolve(), filename)


@app.route("/api/attachments/<path:filename>", methods=["DELETE"])
def delete_attachment(filename: str):
    filename = secure_filename(filename)
    path = ATTACHMENTS_DIR / filename
    if path.is_file():
        path.unlink()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not found"}), 404


def _stream_run() -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "src.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        with _run_lock:
            _run_state["lines"].append(line.rstrip("\n"))
    process.wait()
    with _run_lock:
        _run_state["running"] = False
        _run_state["returncode"] = process.returncode


@app.route("/api/run", methods=["POST"])
def start_run():
    with _run_lock:
        if _run_state["running"]:
            return jsonify({"ok": False, "error": "already running"}), 409
        _run_state["running"] = True
        _run_state["lines"] = []
        _run_state["returncode"] = None
    threading.Thread(target=_stream_run, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/run/status", methods=["GET"])
def run_status():
    since = request.args.get("since", default=0, type=int)
    with _run_lock:
        lines = _run_state["lines"][since:]
        return jsonify(
            {
                "running": _run_state["running"],
                "returncode": _run_state["returncode"],
                "lines": lines,
                "total": len(_run_state["lines"]),
            }
        )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
