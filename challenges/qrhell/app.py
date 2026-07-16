import base64
import binascii
import os
import re
import secrets
import sqlite3
from functools import wraps
from io import BytesIO

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from PIL import Image
from pyzbar.pyzbar import decode as decode_qr
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(12).hex())
DATABASE = os.environ.get("DATABASE", "/app/data/challenge.db")
FLAG = "BHCTF{r3v0lut10n_1n_acces1bilit7}"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    admin_password = secrets.token_urlsafe(24)
    existing = db.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if existing is None:
        db.execute(
            "INSERT INTO users (username, password, is_admin) VALUES (?, ?, 1)",
            ("admin", admin_password),
        )
    db.commit()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        if "user_id" not in session:
            flash("Authentication required. Please authenticate with the ULAE gateway.", "error")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped


def png_bytes_from_b64(payload: str) -> bytes | None:
    if not payload:
        return None
    text = payload.strip()
    if text.startswith("data:") and "," in text:
        text = text.split(",", 1)[1]
    text = re.sub(r"\s+", "", text)
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        return None


def decode_password_png(png_bytes: bytes) -> str | None:
    image = Image.open(BytesIO(png_bytes)).convert("RGB")
    codes = decode_qr(image)
    if not codes:
        return None
    return codes[0].data.decode("utf-8", errors="replace")


def lookup_user(username: str, password: str):
    db = get_db()
    query = (
        "SELECT id, username, is_admin FROM users "
        f"WHERE username = '{username}' AND password = '{password}'"
    )
    return db.execute(query).fetchone()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Official username and authorized access phrase are required.", "error")
            return render_template("register.html")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password, is_admin) VALUES (?, ?, 0)",
                (username, password),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("This username is already enrolled with the EU Authority.", "error")
            return render_template("register.html")

        flash("Enrollment accepted. Authenticate by drawing your access phrase as a QR matrix.", "ok")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.is_json:
            data = request.get_json(silent=True) or {}
            username = (data.get("username") or "").strip()
            png_b64 = data.get("password_png_b64") or ""
        else:
            username = (request.form.get("username") or "").strip()
            png_b64 = request.form.get("password_png_b64") or ""

        if not username or not png_b64:
            flash("Official username and visual access matrix are required.", "error")
            return render_template("login.html")

        png_bytes = png_bytes_from_b64(png_b64)
        if png_bytes is None:
            flash("Visual matrix payload is not valid base64.", "error")
            return render_template("login.html")

        password = decode_password_png(png_bytes)
        if password is None:
            flash("Commission auditors could not decode your matrix. Verify modules and quiet zone.", "error")
            return render_template("login.html")

        row = lookup_user(username, password)
        if row is None:
            flash("Authentication failed. Citizen credentials not recognised by ULAE.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = row["id"]
        session["username"] = row["username"]
        session["is_admin"] = bool(row["is_admin"])
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        username=session.get("username"),
        is_admin=session.get("is_admin"),
        flag=FLAG if session.get("is_admin") else None,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
