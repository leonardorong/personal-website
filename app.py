from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-me-please"  # required for flash messages

@app.route("/")
def home():
    return render_template(
        "index.html",
        title="Leonard Rongoma — Rongoma KE",
        year=datetime.now().year
    )

@app.post("/contact")
def contact():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not email or not message:
        flash("Please fill in all fields.", "danger")
        return redirect(url_for("home") + "#contact")

    # Simple handling: print to server log (you can later email or store in DB)
    print(f"[CONTACT] {name} <{email}>: {message}")

    flash("Thanks for reaching out! I’ll get back to you shortly.", "success")
    return redirect(url_for("home") + "#contact")

if __name__ == "__main__":
    app.run(debug=True)
