"""
CampusPulse - Campus Issue Reporting Platform
app.py — PostgreSQL version (migrated from SQLite)
"""

import os
import json
import urllib.request
import urllib.error
from functools import wraps
from datetime import datetime
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, session)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
from psycopg2 import pool

# Load environment variables from .env file (never commit this file!)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — env vars must be set manually

app = Flask(__name__)

# ── Secret key (used to sign session cookies) ──────────────────────────────────
app.secret_key = os.environ.get("SECRET_KEY", "")

# ── Admin credentials (set these in your .env file!) ────────────────────────────
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# ── Groq API ─────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

NOVA_SYSTEM_PROMPT = """
You are NOVA, the official AI assistant for Vignan's CampusPulse — 
a campus issue reporting and tracking platform for Vignan's University students.

Your name is NOVA. If anyone asks who you are, say:
"I'm NOVA, the AI assistant for Vignan's CampusPulse! 🤖 Here to help you report 
issues, track complaints, and navigate the platform."

=== ABOUT THE PLATFORM ===
CampusPulse allows students to report campus problems, track their resolution, 
earn points, and compete on a leaderboard. Admins manage and resolve complaints.

=== HOW TO USE THE PLATFORM ===
1. REGISTER: Go to the entry page, click "I'm a Student", register with your 
   Registration ID (e.g. 22FA1B0001), full name, email and password.
2. LOGIN: Use your Registration ID and password to log in.
3. REPORT AN ISSUE: Click "Report an Issue" in the navbar. Fill in:
   - Issue Title (be specific)
   - Category (Infrastructure, Technology, Hygiene, Academic, Safety, Transport, Other)
   - Block (A-Block, H-Block, P-Block, N-Block, U-Block, Library, Boys Hostel, Girls Hostel)
   - Exact location description (e.g. "3rd floor, near Room 304")
   - Description of the problem
   - Optional photo (earns bonus points)
4. TRACK: Go to "Issues" page to see all complaints and their status.
5. COMMENT: Click "Comments" on any complaint to discuss it.
6. PROFILE: See your points, badge, complaint history and achievements.
7. LEADERBOARD: See top student contributors ranked by points.

=== COMPLAINT STATUS ===
- Pending: Submitted, waiting for admin review
- In Progress: Admin is working on it
- Resolved: Issue has been fixed

=== POINTS SYSTEM ===
- Submit a complaint: +10 points
- Add a photo to complaint: +5 points
- Your complaint gets resolved: +15 points
- Upvote another complaint: +2 points

=== BADGES ===
- Newcomer: 0-49 points
- Reporter: 50-149 points
- Advocate: 150-299 points
- Champion: 300-499 points
- Legend: 500+ points

=== BLOCKS / LOCATIONS ===
A-Block, H-Block, P-Block, N-Block, U-Block, Library, Boys Hostel, Girls Hostel

=== CATEGORIES ===
- Infrastructure: broken furniture, water issues, electrical, building damage
- Technology: Wi-Fi, projectors, computers, lab equipment
- Hygiene: washrooms, garbage, cleanliness
- Academic: classroom issues, timetable, faculty concerns
- Safety: security, lighting, hazards
- Transport: buses, parking, roads
- Other: anything that doesn't fit above

=== ADMIN PANEL ===
Only admins can access /admin. Admin credentials are set by the institution.
Admin can update complaint status, post official replies (shown with verified tick),
view charts by category/status/timeline, and filter complaints by block.

=== PRIVACY ===
Student identities are completely private. Admins only see complaints as "Anonymous".
Your name is never shown to the admin — only your complaint content.

=== RULES ===
- Only registered students can submit complaints and comment
- One upvote per complaint per student
- Comments do not earn points
- Be factual and respectful in complaints

=== NOVA'S BEHAVIOR ===
- Always introduce yourself as NOVA when greeted
- Be friendly, warm, and encouraging — like a helpful senior student
- Use light emojis occasionally to keep the tone friendly 🎯
- Guide students step by step when they are confused
- If asked about something not related to CampusPulse or Vignan's University,
  politely say: "I'm NOVA and I'm only trained to assist with CampusPulse! 
  For other queries, please reach out to your faculty. 😊"
- Never make up complaint statuses or student data — you don't have live DB access
- If a student seems frustrated, be empathetic: acknowledge their issue and 
  reassure them it will be seen by the admin team
- Always remind students to add photos for bonus points
- Encourage students to upvote issues they relate to
- Respond in the same language the student uses (English or Telugu-English mix is fine)
- Keep replies concise — no long paragraphs unless the student needs step-by-step help
"""

UPLOAD_FOLDER      = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["UPLOAD_FOLDER"]      = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost:5432/campuspulse")

POINTS_SUBMIT   = 10
POINTS_PHOTO    = 5
POINTS_RESOLVED = 15
POINTS_UPVOTE   = 2
MAX_BLOCKS      = 3   # blocks before permanent ban

def badge_for(points):
    if points >= 500: return "Legend"
    if points >= 300: return "Champion"
    if points >= 150: return "Advocate"
    if points >= 50:  return "Reporter"
    return "Newcomer"

# ── DB (Connection Pool for heavy traffic) ─────────────────────────────────────
connection_pool = None

def init_pool():
    global connection_pool
    connection_pool = pool.ThreadedConnectionPool(
        minconn=5,
        maxconn=20,
        dsn=DATABASE_URL
    )

def get_db():
    global connection_pool

    try:
        conn = connection_pool.getconn()

        # Check if the connection is still alive
        with conn.cursor() as cur:
            cur.execute("SELECT 1")

        return conn

    except Exception as e:
        print("Reinitializing connection pool:", e)

        try:
            connection_pool.closeall()
        except:
            pass

        init_pool()
        return connection_pool.getconn()

def release_db(conn):
    connection_pool.putconn(conn)

def dict_cur(conn):
    """Return a cursor that yields dict-like rows (same as sqlite3.Row)."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id            SERIAL  PRIMARY KEY,
            regd_id       TEXT    NOT NULL UNIQUE,
            full_name     TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            points        INTEGER NOT NULL DEFAULT 0,
            badge         TEXT    NOT NULL DEFAULT 'Newcomer',
            joined_at     TEXT    NOT NULL,
            block_count   INTEGER NOT NULL DEFAULT 0,
            is_banned     INTEGER NOT NULL DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id           SERIAL  PRIMARY KEY,
            title        TEXT    NOT NULL,
            description  TEXT    NOT NULL,
            category     TEXT    NOT NULL,
            status       TEXT    NOT NULL DEFAULT 'Pending',
            image_path   TEXT,
            student_id   INTEGER,
            location     TEXT    NOT NULL DEFAULT 'Not Specified',
            upvotes      INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT    NOT NULL,
            is_blocked   INTEGER NOT NULL DEFAULT 0,
            block_reason TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS upvotes (
            student_id   INTEGER NOT NULL,
            complaint_id INTEGER NOT NULL,
            PRIMARY KEY (student_id, complaint_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id           SERIAL  PRIMARY KEY,
            complaint_id INTEGER NOT NULL,
            student_id   INTEGER,
            is_admin     INTEGER NOT NULL DEFAULT 0,
            body         TEXT    NOT NULL,
            created_at   TEXT    NOT NULL,
            FOREIGN KEY (complaint_id) REFERENCES complaints(id),
            FOREIGN KEY (student_id)   REFERENCES students(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id           SERIAL  PRIMARY KEY,
            student_id   INTEGER NOT NULL,
            type         TEXT    NOT NULL,
            title        TEXT    NOT NULL,
            message      TEXT    NOT NULL,
            complaint_id INTEGER,
            is_read      INTEGER NOT NULL DEFAULT 0,
            created_at   TEXT    NOT NULL,
            FOREIGN KEY (student_id)   REFERENCES students(id),
            FOREIGN KEY (complaint_id) REFERENCES complaints(id)
        )
    """)

    # Safe migrations for existing DBs (PostgreSQL style)
    migrations = [
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT 'Not Specified'",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS is_blocked INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE complaints ADD COLUMN IF NOT EXISTS block_reason TEXT",
        "ALTER TABLE students   ADD COLUMN IF NOT EXISTS block_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE students   ADD COLUMN IF NOT EXISTS is_banned   INTEGER NOT NULL DEFAULT 0",
    ]
    for sql in migrations:
        try:
            c.execute(sql)
            conn.commit()
        except Exception:
            conn.rollback()

    conn.commit()
    c.close()
    release_db(conn)

def allowed_file(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def add_points(student_id, pts):
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute("UPDATE students SET points = points + %s WHERE id = %s", (pts, student_id))
    cur.execute("SELECT points FROM students WHERE id = %s", (student_id,))
    new_pts = cur.fetchone()["points"]
    cur.execute("UPDATE students SET badge = %s WHERE id = %s", (badge_for(new_pts), student_id))
    conn.commit()
    cur.close()
    release_db(conn)

# ── Notification helper ───────────────────────────────────────────────────────
def push_notification(student_id, notif_type, title, message, complaint_id=None):
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute(
        """INSERT INTO notifications
               (student_id, type, title, message, complaint_id, is_read, created_at)
           VALUES (%s,%s,%s,%s,%s,0,%s)""",
        (student_id, notif_type, title, message, complaint_id,
         datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    cur.close()
    release_db(conn)

# ── Auth decorators ───────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("admin_logged_in"):
            flash("Please log in to access the admin panel.", "error")
            return redirect(url_for("admin_login"))
        return f(*a, **kw)
    return wrap

def student_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("student_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("student_login"))
        conn = get_db()
        cur = dict_cur(conn)
        cur.execute("SELECT is_banned FROM students WHERE id = %s", (session["student_id"],))
        row = cur.fetchone()
        cur.close()
        release_db(conn)
        if row and row["is_banned"]:
            session.clear()
            flash("Your account has been permanently banned due to repeated violations.", "error")
            return redirect(url_for("entry"))
        return f(*a, **kw)
    return wrap

# ── Context processor ─────────────────────────────────────────────────────────
@app.context_processor
def inject_student():
    student      = None
    unread_count = 0
    if session.get("student_id"):
        try:
            conn = get_db()
            cur = dict_cur(conn)
            cur.execute(
                "SELECT id, regd_id, full_name, points, badge, block_count, is_banned FROM students WHERE id = %s",
                (session["student_id"],)
            )
            student = cur.fetchone()
            if student:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM notifications WHERE student_id=%s AND is_read=0",
                    (student["id"],)
                )
                row = cur.fetchone()
                unread_count = row["cnt"] if row else 0
            cur.close()
            release_db(conn)
        except Exception:
            pass
        if not student:
            session.pop("student_id", None)
    return {
        "current_student": student,
        "unread_count":    unread_count,
        "now_ts":          datetime.now().strftime("%Y-%m-%d %H:%M"),
        "MAX_BLOCKS":      MAX_BLOCKS,
    }

# ═════════════════════════════════════════════════════════════════════════════
#  ENTRY / AUTH
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/")
def entry():
    if session.get("student_id"):
        return redirect(url_for("dashboard"))
    if session.get("admin_logged_in"):
        return redirect(url_for("admin"))
    return render_template("entry.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("student_id"):
        return redirect(url_for("profile"))
    if request.method == "POST":
        regd_id   = request.form.get("regd_id",   "").strip().upper()
        full_name = request.form.get("full_name",  "").strip()
        email     = request.form.get("email",      "").strip().lower()
        password  = request.form.get("password",   "").strip()
        confirm   = request.form.get("confirm",    "").strip()
        if not all([regd_id, full_name, email, password, confirm]):
            flash("All fields are required.", "error"); return redirect(url_for("register"))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error"); return redirect(url_for("register"))
        if password != confirm:
            flash("Passwords do not match.", "error"); return redirect(url_for("register"))
        conn = get_db()
        cur = dict_cur(conn)
        cur.execute("SELECT id FROM students WHERE regd_id=%s", (regd_id,))
        if cur.fetchone():
            cur.close(); release_db(conn); flash("Registration ID already exists.", "error"); return redirect(url_for("register"))
        cur.execute("SELECT id FROM students WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close(); release_db(conn); flash("Email already registered.", "error"); return redirect(url_for("register"))
        cur.execute(
            "INSERT INTO students (regd_id,full_name,email,password_hash,joined_at) VALUES (%s,%s,%s,%s,%s)",
            (regd_id, full_name, email, generate_password_hash(password),
             datetime.now().strftime("%Y-%m-%d"))
        )
        conn.commit()
        cur.execute("SELECT id FROM students WHERE regd_id=%s", (regd_id,))
        sid = cur.fetchone()["id"]
        cur.close()
        release_db(conn)
        push_notification(sid, "registered", "Welcome to CampusPulse! 🎉",
            f"Hi {full_name}! Your account is ready. Your Registration ID is {regd_id} — keep it safe. "
            "You can now report campus issues and earn points!")
        flash("Account created! Please log in.", "success")
        return redirect(url_for("student_login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def student_login():
    if session.get("student_id"):
        return redirect(url_for("profile"))
    if request.method == "POST":
        regd_id  = request.form.get("regd_id",  "").strip().upper()
        password = request.form.get("password", "").strip()
        conn = get_db()
        cur = dict_cur(conn)
        cur.execute("SELECT * FROM students WHERE regd_id=%s", (regd_id,))
        s = cur.fetchone()
        cur.close()
        release_db(conn)
        if s and check_password_hash(s["password_hash"], password):
            if s["is_banned"]:
                flash("Your account has been permanently banned due to repeated violations.", "error")
                return redirect(url_for("student_login"))
            session["student_id"]   = s["id"]
            session["student_name"] = s["full_name"]
            session["student_regd"] = s["regd_id"]
            flash(f"Welcome back, {s['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid Registration ID or password.", "error")
    return render_template("student_login.html")

@app.route("/logout")
def student_logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("entry"))

# ═════════════════════════════════════════════════════════════════════════════
#  STUDENT ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/dashboard")
@student_required
def dashboard():
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute("SELECT COUNT(*) AS cnt FROM complaints WHERE is_blocked=0"); total = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM complaints WHERE status='Resolved' AND is_blocked=0"); resolved = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM complaints WHERE status='In Progress' AND is_blocked=0"); in_progress = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM complaints WHERE status='Pending' AND is_blocked=0"); pending = cur.fetchone()["cnt"]
    cur.execute("SELECT * FROM complaints WHERE is_blocked=0 ORDER BY id DESC LIMIT 3"); recent = cur.fetchall()
    cur.close()
    release_db(conn)
    stats = {"total": total, "resolved": resolved, "in_progress": in_progress, "pending": pending}
    return render_template("index.html", stats=stats, recent=recent)

@app.route("/complaints")
def complaints():
    cat_f    = request.args.get("category", "All")
    status_f = request.args.get("status",   "All")
    query    = "SELECT * FROM complaints WHERE is_blocked=0"
    params   = []
    if cat_f    != "All": query += " AND category=%s"; params.append(cat_f)
    if status_f != "All": query += " AND status=%s";   params.append(status_f)
    query += " ORDER BY id DESC"
    conn  = get_db()
    cur = dict_cur(conn)
    cur.execute(query, params)
    items = cur.fetchall()
    cur.close()
    release_db(conn)
    categories = ["All","Infrastructure","Technology","Hygiene","Academic","Safety","Transport","Other"]
    statuses   = ["All","Pending","In Progress","Resolved"]
    return render_template("complaints.html", complaints=items, categories=categories,
                           statuses=statuses, active_category=cat_f, active_status=status_f)

@app.route("/submit", methods=["GET", "POST"])
@student_required
def submit():
    if request.method == "POST":
        title         = request.form.get("title",       "").strip()
        description   = request.form.get("description", "").strip()
        category      = request.form.get("category",    "").strip()
        block         = request.form.get("block",       "").strip()
        location_desc = request.form.get("location",    "").strip()
        location = f"{block} — {location_desc}" if block and location_desc else (block or location_desc or "Not Specified")
        student_id = session["student_id"]
        if not title or not description or not category or not block:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("submit"))
        image_path, has_photo = None, False
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename and allowed_file(file.filename):
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                image_path = f"uploads/{filename}"
                has_photo  = True
        conn = get_db()
        cur = dict_cur(conn)
        cur.execute(
            "INSERT INTO complaints (title,description,category,location,status,image_path,student_id,created_at) VALUES (%s,%s,%s,%s,'Pending',%s,%s,%s) RETURNING id",
            (title, description, category, location, image_path, student_id,
             datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        cid = cur.fetchone()["id"]
        conn.commit()
        cur.close()
        release_db(conn)
        pts = POINTS_SUBMIT + (POINTS_PHOTO if has_photo else 0)
        add_points(student_id, pts)
        push_notification(student_id, "complaint_submitted",
            "Complaint Submitted Successfully ✅",
            f"Your complaint \"{title}\" has been received and is now under review. "
            f"You earned +{pts} points. We'll notify you when there's an update.",
            complaint_id=cid)
        flash(f"Complaint submitted! You earned +{pts} points.", "success")
        return redirect(url_for("dashboard"))
    return render_template("submit.html")

@app.route("/profile")
@student_required
def profile():
    sid  = session["student_id"]
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute("SELECT * FROM students WHERE id=%s", (sid,))
    student = cur.fetchone()
    if not student:
        cur.close(); release_db(conn); session.clear()
        flash("Session expired.", "error"); return redirect(url_for("student_login"))
    cur.execute("SELECT * FROM complaints WHERE student_id=%s ORDER BY id DESC", (sid,))
    my_complaints = cur.fetchall()
    cur.execute(
        "SELECT COUNT(*)+1 AS rank FROM students WHERE points>(SELECT points FROM students WHERE id=%s)", (sid,)
    )
    rank_row = cur.fetchone()
    cur.execute("SELECT COUNT(*) AS cnt FROM students")
    total_students = cur.fetchone()["cnt"]
    cur.close()
    release_db(conn)
    return render_template("profile.html", student=student, my_complaints=my_complaints,
                           rank=rank_row["rank"], total_students=total_students)

# ── Notifications ─────────────────────────────────────────────────────────────
@app.route("/notifications")
@student_required
def notifications():
    sid  = session["student_id"]
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute("SELECT * FROM notifications WHERE student_id=%s ORDER BY id DESC", (sid,))
    notifs = cur.fetchall()
    cur.execute("UPDATE notifications SET is_read=1 WHERE student_id=%s", (sid,))
    conn.commit()
    cur.close()
    release_db(conn)
    return render_template("notifications.html", notifications=notifs)

@app.route("/api/notifications/mark-read", methods=["POST"])
@student_required
def mark_notifications_read():
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute("UPDATE notifications SET is_read=1 WHERE student_id=%s", (session["student_id"],))
    conn.commit()
    cur.close()
    release_db(conn)
    return jsonify({"ok": True})

# ── Leaderboard ───────────────────────────────────────────────────────────────
@app.route("/leaderboard")
def leaderboard():
    conn  = get_db()
    cur = dict_cur(conn)
    cur.execute("""
        SELECT s.id,s.regd_id,s.full_name,s.points,s.badge,s.joined_at,s.is_banned,
               COUNT(c.id) AS complaint_count
        FROM   students s LEFT JOIN complaints c ON c.student_id=s.id AND c.is_blocked=0
        WHERE  s.is_banned=0
        GROUP  BY s.id ORDER BY s.points DESC LIMIT 20
    """)
    users = cur.fetchall()
    cur.close()
    release_db(conn)
    return render_template("leaderboard.html", users=users)

# ── Complaint detail + comments ───────────────────────────────────────────────
@app.route("/complaint/<int:complaint_id>")
def complaint_detail(complaint_id):
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute("SELECT * FROM complaints WHERE id=%s", (complaint_id,))
    c = cur.fetchone()
    if not c or c["is_blocked"]:
        cur.close(); release_db(conn); flash("This complaint is not available.", "error")
        return redirect(url_for("complaints"))
    cur.execute(
        "SELECT id,is_admin,body,created_at FROM comments WHERE complaint_id=%s ORDER BY is_admin DESC,created_at ASC",
        (complaint_id,)
    )
    comments = cur.fetchall()
    cur.close()
    release_db(conn)
    return render_template("complaint_detail.html", complaint=c, comments=comments)

@app.route("/complaint/<int:complaint_id>/comment", methods=["POST"])
@student_required
def add_comment(complaint_id):
    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("complaint_detail", complaint_id=complaint_id))
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute(
        "INSERT INTO comments (complaint_id,student_id,is_admin,body,created_at) VALUES (%s,%s,0,%s,%s)",
        (complaint_id, session["student_id"], body, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    cur.close()
    release_db(conn)
    return redirect(url_for("complaint_detail", complaint_id=complaint_id) + "#comments")

@app.route("/api/upvote/<int:complaint_id>", methods=["POST"])
@student_required
def upvote(complaint_id):
    sid  = session["student_id"]
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute("SELECT 1 FROM upvotes WHERE student_id=%s AND complaint_id=%s", (sid, complaint_id))
    if cur.fetchone():
        cur.close(); release_db(conn); return jsonify({"error": "already_upvoted"}), 400
    cur.execute("INSERT INTO upvotes (student_id,complaint_id) VALUES (%s,%s)", (sid, complaint_id))
    cur.execute("UPDATE complaints SET upvotes=upvotes+1 WHERE id=%s", (complaint_id,))
    conn.commit()
    cur.execute("SELECT upvotes FROM complaints WHERE id=%s", (complaint_id,))
    new_count = cur.fetchone()
    cur.close()
    release_db(conn)
    add_points(sid, POINTS_UPVOTE)
    return jsonify({"upvotes": new_count["upvotes"]})

@app.route("/chat")
def chat():
    return render_template("chat.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Proxy to Groq API — keeps API key server-side, never exposed to browser."""
    data     = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    history  = data.get("history") or []

    if not user_msg:
        return jsonify({"error": "empty message"}), 400

    if not GROQ_API_KEY:
        return jsonify({"error": "AI not configured. Add GROQ_API_KEY to your .env file."}), 503

    # Build messages array for Groq (OpenAI-compatible format)
    messages = [{"role": "system", "content": NOVA_SYSTEM_PROMPT}]

    # Add conversation history (last 10 turns)
    for turn in history[-10:]:
        role = "user" if turn.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": turn.get("text", "")})

    # Add current user message
    messages.append({"role": "user", "content": user_msg})

    payload = json.dumps({
        "model":       GROQ_MODEL,
        "messages":    messages,
        "temperature": 0.7,
        "max_tokens":  500,
    }).encode("utf-8")

    url = "https://api.groq.com/openai/v1/chat/completions"

    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        reply = result["choices"][0]["message"]["content"]
        return jsonify({"reply": reply})
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        return jsonify({"error": f"Groq API error: {e.code} — {err[:200]}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ═════════════════════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin"))
    if request.method == "POST":
        if request.form.get("username","").strip() == ADMIN_USERNAME and \
           request.form.get("password","").strip() == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            flash("Welcome back, Admin!", "success")
            return redirect(url_for("admin"))
        flash("Incorrect credentials.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        cid        = request.form.get("complaint_id")
        new_status = request.form.get("status")
        ab         = request.form.get("active_block", "")

        if cid and new_status in ["Pending", "In Progress", "Resolved"]:
            conn = get_db()
            cur = dict_cur(conn)
            cur.execute("SELECT student_id,status,title FROM complaints WHERE id=%s", (cid,))
            complaint = cur.fetchone()
            cur.execute("UPDATE complaints SET status=%s WHERE id=%s", (new_status, cid))
            conn.commit()
            if complaint and complaint["student_id"]:
                sid, title = complaint["student_id"], complaint["title"]
                if new_status == "Resolved" and complaint["status"] != "Resolved":
                    add_points(sid, POINTS_RESOLVED)
                    push_notification(sid, "resolved", "Your Complaint Has Been Resolved ✅",
                        f"Great news! \"{title}\" is now Resolved. "
                        f"You earned +{POINTS_RESOLVED} bonus points. Thank you!", complaint_id=int(cid))
                elif new_status == "In Progress" and complaint["status"] == "Pending":
                    push_notification(sid, "admin_replied", "Your Complaint Is Being Worked On 🔧",
                        f"Your complaint \"{title}\" is now In Progress. The team is on it.",
                        complaint_id=int(cid))
            cur.close()
            release_db(conn)
            flash(f"Status updated to '{new_status}'.", "success")

        redir = url_for("admin") + (f"?block={ab}#blockSection" if ab else "")
        return redirect(redir)

    # GET
    active_block = request.args.get("block", "").strip()
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute(
        "SELECT c.*, s.regd_id as student_regd, s.full_name as student_name, "
        "s.block_count, s.is_banned "
        "FROM complaints c LEFT JOIN students s ON c.student_id=s.id "
        "ORDER BY c.id DESC"
    )
    items = cur.fetchall()

    cur.execute("SELECT COUNT(*) AS cnt FROM complaints WHERE is_blocked=0"); total = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM complaints WHERE status='Pending' AND is_blocked=0"); pending = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM complaints WHERE status='In Progress' AND is_blocked=0"); in_progress = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM complaints WHERE status='Resolved' AND is_blocked=0"); resolved = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM students"); students_cnt = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM complaints WHERE is_blocked=1"); blocked = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM students WHERE is_banned=1"); banned = cur.fetchone()["cnt"]

    counts = {
        "total": total, "pending": pending, "in_progress": in_progress,
        "resolved": resolved, "students": students_cnt, "blocked": blocked, "banned": banned,
    }

    cur.execute(
        "SELECT CAST(ROUND(AVG(NOW()::date - TO_DATE(SUBSTRING(created_at,1,10),'YYYY-MM-DD'))) AS INTEGER) AS avg_days "
        "FROM complaints WHERE status='Resolved'"
    )
    avg_row = cur.fetchone()
    counts["avg_resolution_days"] = avg_row["avg_days"] if avg_row and avg_row["avg_days"] else None

    block_complaints = []
    if active_block:
        cur.execute(
            "SELECT c.*, s.regd_id as student_regd, s.block_count, s.is_banned "
            "FROM complaints c LEFT JOIN students s ON c.student_id=s.id "
            "WHERE c.location LIKE %s ORDER BY c.id DESC",
            (f"{active_block}%",)
        )
        block_complaints = cur.fetchall()

    cur.execute("SELECT category,COUNT(*) AS cnt FROM complaints WHERE is_blocked=0 GROUP BY category ORDER BY cnt DESC")
    cat_rows = cur.fetchall()
    cur.execute(
        "SELECT SUBSTRING(created_at,1,10) AS day,COUNT(*) AS cnt FROM complaints "
        "WHERE created_at >= to_char(NOW() - INTERVAL '14 days','YYYY-MM-DD') AND is_blocked=0 GROUP BY day ORDER BY day"
    )
    daily_rows = cur.fetchall()
    cur.close()
    release_db(conn)

    return render_template("admin.html",
        complaints=items, counts=counts,
        active_block=active_block, block_complaints=block_complaints,
        chart_categories=[r["category"] for r in cat_rows],
        chart_cat_counts=[r["cnt"] for r in cat_rows],
        chart_status_counts=[counts["pending"], counts["in_progress"], counts["resolved"]],
        chart_days=[r["day"] for r in daily_rows],
        chart_day_counts=[r["cnt"] for r in daily_rows],
    )

# ── Admin: Block a complaint ──────────────────────────────────────────────────
@app.route("/admin/complaint/<int:complaint_id>/block", methods=["POST"])
@admin_required
def block_complaint(complaint_id):
    reason = request.form.get("reason", "Spam or abusive content").strip() or "Spam or abusive content"
    ab     = request.form.get("active_block", "")
    conn   = get_db()
    cur = dict_cur(conn)
    cur.execute("SELECT student_id, title, is_blocked FROM complaints WHERE id=%s", (complaint_id,))
    complaint = cur.fetchone()

    if not complaint or complaint["is_blocked"]:
        cur.close(); release_db(conn)
        flash("Complaint already blocked or not found.", "error")
        return redirect(url_for("admin") + (f"?block={ab}#blockSection" if ab else ""))

    cur.execute("UPDATE complaints SET is_blocked=1, block_reason=%s WHERE id=%s", (reason, complaint_id))
    conn.commit()

    sid = complaint["student_id"]
    new_count = 0
    if sid:
        cur.execute("UPDATE students SET block_count=block_count+1 WHERE id=%s", (sid,))
        conn.commit()
        cur.execute("SELECT block_count, full_name, is_banned FROM students WHERE id=%s", (sid,))
        student = cur.fetchone()
        new_count = student["block_count"]
        remaining = MAX_BLOCKS - new_count

        if new_count >= MAX_BLOCKS and not student["is_banned"]:
            cur.execute("UPDATE students SET is_banned=1 WHERE id=%s", (sid,))
            conn.commit()
            push_notification(sid, "banned",
                "⛔ Your Account Has Been Banned",
                f"Your account has been permanently banned after receiving {MAX_BLOCKS} content violations. "
                "Your complaint access has been revoked. Contact admin if you believe this is a mistake.")
        else:
            if remaining == 2:
                warn_title = "⚠️ Warning: Your Complaint Was Removed (1/{})".format(MAX_BLOCKS)
                warn_msg   = (
                    f"Your complaint \"{complaint['title']}\" was removed by admin for: {reason}. "
                    f"This is your 1st violation. You have {remaining} more before your account is permanently banned."
                )
            elif remaining == 1:
                warn_title = "🚨 Final Warning: One More Violation = Ban (2/{})".format(MAX_BLOCKS)
                warn_msg   = (
                    f"Your complaint \"{complaint['title']}\" was removed for: {reason}. "
                    "This is your FINAL warning. One more violation will permanently ban your account."
                )
            else:
                warn_title = f"⚠️ Complaint Removed — Violation {new_count}/{MAX_BLOCKS}"
                warn_msg   = (
                    f"Your complaint \"{complaint['title']}\" was removed for: {reason}. "
                    f"Violation {new_count} of {MAX_BLOCKS} recorded."
                )
            push_notification(sid, "warning", warn_title, warn_msg, complaint_id=complaint_id)

    cur.close()
    release_db(conn)
    flash(f"Complaint blocked. Student now has {new_count}/{MAX_BLOCKS} violations.", "success")
    return redirect(url_for("admin") + (f"?block={ab}#blockSection" if ab else ""))

# ── Admin: Unblock a complaint ────────────────────────────────────────────────
@app.route("/admin/complaint/<int:complaint_id>/unblock", methods=["POST"])
@admin_required
def unblock_complaint(complaint_id):
    ab   = request.form.get("active_block", "")
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute("SELECT student_id, title, is_blocked FROM complaints WHERE id=%s", (complaint_id,))
    complaint = cur.fetchone()

    if not complaint or not complaint["is_blocked"]:
        cur.close(); release_db(conn)
        flash("Complaint is not blocked.", "error")
        return redirect(url_for("admin") + (f"?block={ab}#blockSection" if ab else ""))

    cur.execute("UPDATE complaints SET is_blocked=0, block_reason=NULL WHERE id=%s", (complaint_id,))
    conn.commit()

    sid = complaint["student_id"]
    if sid:
        cur.execute("UPDATE students SET block_count=GREATEST(0, block_count-1) WHERE id=%s", (sid,))
        conn.commit()
        push_notification(sid, "unblocked",
            "✅ Your Complaint Has Been Reinstated",
            f"Good news! Your complaint \"{complaint['title']}\" has been reviewed and restored. "
            "A previous violation has been reversed.",
            complaint_id=complaint_id)

    cur.close()
    release_db(conn)
    flash("Complaint unblocked and violation count reduced.", "success")
    return redirect(url_for("admin") + (f"?block={ab}#blockSection" if ab else ""))

# ── Admin: Unban a student ────────────────────────────────────────────────────
@app.route("/admin/student/<int:student_id>/unban", methods=["POST"])
@admin_required
def unban_student(student_id):
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute("SELECT full_name, is_banned FROM students WHERE id=%s", (student_id,))
    student = cur.fetchone()
    if student and student["is_banned"]:
        cur.execute("UPDATE students SET is_banned=0, block_count=0 WHERE id=%s", (student_id,))
        conn.commit()
        push_notification(student_id, "unbanned",
            "✅ Your Account Has Been Reinstated",
            "Your account ban has been lifted by the admin. Your violation record has been cleared. "
            "Please ensure your future submissions follow the community guidelines.")
        flash(f"Student {student['full_name']} has been unbanned.", "success")
    else:
        flash("Student not found or not banned.", "error")
    cur.close()
    release_db(conn)
    return redirect(url_for("admin_students"))

# ── Admin: Students management page ──────────────────────────────────────────
@app.route("/admin/students")
@admin_required
def admin_students():
    conn = get_db()
    cur = dict_cur(conn)
    cur.execute(
        "SELECT s.*, COUNT(c.id) AS total_complaints, "
        "SUM(CASE WHEN c.is_blocked=1 THEN 1 ELSE 0 END) AS blocked_complaints "
        "FROM students s LEFT JOIN complaints c ON c.student_id=s.id "
        "GROUP BY s.id ORDER BY s.is_banned DESC, s.block_count DESC, s.id DESC"
    )
    students = cur.fetchall()
    cur.close()
    release_db(conn)
    return render_template("admin_students.html", students=students, MAX_BLOCKS=MAX_BLOCKS)

# ── Admin: Reply ──────────────────────────────────────────────────────────────
@app.route("/admin/complaint/<int:complaint_id>/reply", methods=["POST"])
@admin_required
def admin_reply(complaint_id):
    body = request.form.get("body", "").strip()
    if body:
        conn = get_db()
        cur = dict_cur(conn)
        cur.execute(
            "INSERT INTO comments (complaint_id,student_id,is_admin,body,created_at) VALUES (%s,NULL,1,%s,%s)",
            (complaint_id, body, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        cur.execute("SELECT student_id,title FROM complaints WHERE id=%s", (complaint_id,))
        complaint = cur.fetchone()
        cur.close()
        release_db(conn)
        if complaint and complaint["student_id"]:
            push_notification(complaint["student_id"], "admin_replied",
                "Admin Replied to Your Complaint 💬",
                f"The admin posted an official reply on \"{complaint['title']}\". Tap to view.",
                complaint_id=complaint_id)
        flash("Reply posted.", "success")
    ab = request.form.get("active_block", "")
    return redirect(url_for("admin") + (f"?block={ab}#blockSection" if ab else ""))

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
init_pool()
init_db()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "True") == "True"
    print("\n✅  CampusPulse running at http://127.0.0.1:5000")
    app.run(debug=debug_mode)
