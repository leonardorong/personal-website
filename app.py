from flask import Flask, render_template, request, redirect, url_for, flash, Response, session, g
from functools import wraps
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os
from werkzeug.security import generate_password_hash

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.secret_key = "123456"  # required for flash messages

DATABASE = "database.db"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # makes rows behave like dicts
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

# Load .env file
load_dotenv()

# Get admin login from environment
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

def update_admins_table():
    db = get_db()
    # check if the column already exists
    try:
        db.execute("ALTER TABLE admins ADD COLUMN force_change INTEGER DEFAULT 0")
        db.commit()
        print("✅ Column force_change added to admins table.")
    except Exception as e:
        print("ℹ️ Column already exists or error:", e)

# ------------------------------
# Ensure default admin exists
# ------------------------------
def init_admin():
    db = get_db()

    # Ensure admins table exists
    db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            force_change INTEGER DEFAULT 1
        )
    """)
    db.commit()

    # Check if any admin exists
    admin_exists = db.execute("SELECT COUNT(*) FROM admins").fetchone()[0]

    if admin_exists == 0:
        default_username = "admin"
        default_password = "admin123"
        hashed_password = generate_password_hash(default_password)

        db.execute(
            "INSERT INTO admins (username, password_hash, force_change) VALUES (?, ?, 1)",
            (default_username, hashed_password)
        )
        db.commit()
        print(f"✅ Default admin created! Username: {default_username}, Password: {default_password} (force password change on first login)")
    else:
        print("ℹ️ Admin already exists. Skipping creation.")


@app.route("/")
def home():
    return render_template(
        "index.html",
        title="Leonard Rongoma — Rongoma KE",
        year=datetime.now().year
    )

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_logged_in" not in session:
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

# ------------------------------
# Admin Login
# ------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            # Store username in session
            session["admin_username"] = user["username"]

            # If the password must be changed (default admin)
            if user["force_change"]:
                return redirect(url_for("force_password_change"))

            # Mark as logged in
            session["admin_logged_in"] = True
            return redirect(url_for("admin_feedback"))

        flash("Invalid username or password", "danger")

    return render_template("admin_login.html")


# ------------------------------
# Force Password Change
# ------------------------------
@app.route("/admin/force-change", methods=["GET", "POST"])
def force_password_change():
    if "admin_username" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            flash("Passwords do not match!", "danger")
        elif len(new_password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db = get_db()
            db.execute(
                "UPDATE admins SET password_hash = ?, force_change = 0 WHERE username = ?",
                (generate_password_hash(new_password), session["admin_username"])
            )
            db.commit()

            # Keep the user logged in after changing password
            session["admin_logged_in"] = True
            flash("Password updated successfully! 🎉", "success")
            return redirect(url_for("admin_feedback"))

    return render_template("force_password_change.html")


# ------------------------------
# Logout
# ------------------------------
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("admin_login"))


# ------------------------------
# Feedback: User submission
# ------------------------------
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        message = request.form["message"]

        db = get_db()
        db.execute(
            "INSERT INTO feedback (name, email, message, created_at) VALUES (?, ?, ?, ?)",
            (name, email, message, datetime.now())
        )
        db.commit()

        flash("✅ Thank you! Your feedback has been received.")
        return redirect(url_for("contact"))

    return render_template("index.html")

# ------------------------------
# Admin: View Feedback
# ------------------------------
@app.route("/admin/feedback")
@login_required
def admin_feedback():
    page = int(request.args.get("page", 1))
    per_page = 10
    offset = (page - 1) * per_page
    search = request.args.get("search", "").strip()

    db = get_db()

    if search:
        total = db.execute(
            "SELECT COUNT(*) FROM feedback WHERE name LIKE ? OR email LIKE ? OR message LIKE ?",
            (f"%{search}%", f"%{search}%", f"%{search}%")
        ).fetchone()[0]

        feedbacks = db.execute(
            """SELECT * FROM feedback
               WHERE name LIKE ? OR email LIKE ? OR message LIKE ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (f"%{search}%", f"%{search}%", f"%{search}%", per_page, offset)
        ).fetchall()
    else:
        total = db.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]

        feedbacks = db.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        ).fetchall()

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "admin_feedback.html",
        feedbacks=feedbacks,
        page=page,
        total_pages=total_pages,
        search=search
    )


# ------------------------------
# Admin: Delete Feedback
# ------------------------------
@app.route("/delete_feedback/<int:feedback_id>", methods=["POST"])
@login_required
def delete_feedback(feedback_id):
    try:
        db = get_db()
        result = db.execute("DELETE FROM feedback WHERE id=?", (feedback_id,))
        db.commit()

        if result.rowcount > 0:
            flash("✅ Feedback deleted successfully!", "success")
        else:
            flash("⚠️ Feedback not found or already deleted.", "danger")

    except Exception as e:
        flash(f"❌ An error occurred: {str(e)}", "danger")

    return redirect(url_for("admin_feedback"))



# ------------------------------
# Admin: Export Feedback PDF
# ------------------------------
@app.route("/admin/feedback/export/pdf")
@login_required
def export_feedback_pdf():
    search = request.args.get("search", "").strip()

    db = get_db()

    if search:
        rows = db.execute(
            """SELECT * FROM feedback 
               WHERE name LIKE ? OR email LIKE ? OR message LIKE ?
               ORDER BY created_at DESC""",
            (f"%{search}%", f"%{search}%", f"%{search}%")
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC"
        ).fetchall()

    # ---- Generate PDF (unchanged logic, just rows use db results) ----
    from io import BytesIO
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    try:
        pdf.drawImage("static/images/logo.png", 40, height - 80, width=60, height=60, preserveAspectRatio=True, mask="auto")
    except:
        pass

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(120, height - 50, "Feedback Report - Rongoma KE")

    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.grey)
    pdf.drawString(120, height - 65, "Generated by Personal Website")
    pdf.setFillColor(colors.black)

    styles = getSampleStyleSheet()
    cell_style = styles["Normal"]
    cell_style.fontSize = 8
    cell_style.leading = 10

    data = [["ID", "Name", "Email", "Message", "Date"]]
    for row in rows:
        message_para = Paragraph(row["message"], cell_style)
        date_para = Paragraph(row["created_at"], cell_style)
        data.append([row["id"], row["name"], row["email"], message_para, date_para])

    left_margin = 40
    right_margin = 40
    available_width = width - (left_margin + right_margin)

    id_width = 40
    name_width = 100
    email_width = 150
    remaining = available_width - (id_width + name_width + email_width)
    message_width = remaining * 0.65
    date_width = remaining * 0.35

    table = Table(data, colWidths=[id_width, name_width, email_width, message_width, date_width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))

    table.wrapOn(pdf, width, height)
    table.drawOn(pdf, left_margin, height - 260)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.grey)
    pdf.drawString(40, 20, f"Generated on: {timestamp}")
    pdf.drawRightString(width - 40, 20, f"Page 1")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    return Response(buffer, mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment;filename=feedback.pdf"})

if __name__ == "__main__":
    with app.app_context():   # ✅ ensures g + db work
        init_admin()          # auto-create default admin if none exists
    app.run(debug=True)

