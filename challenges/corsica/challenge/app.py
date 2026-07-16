import uuid
import time
import traceback
import os
from markupsafe import Markup
from flask import Flask, request, session, redirect, url_for, render_template, flash
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
from threading import Thread

app = Flask(__name__)
app.secret_key = 'super_secret_key_383d142f64454d4a103a'
app.config.update(
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_SECURE=True
)

FLAG = "BHCTF{m3t4_r3fr3sh_b34ts_csp_3very_t1me}"
HOSTNAME_FOR_ADMIN_BOT = "localhost:443"
FLAG_TOKEN_LIFETIME = 5
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "8b8342f930528762934dce5a279d4c8db7c5b625d21b4b688a315633a739"

users = {ADMIN_USERNAME:ADMIN_PASSWORD}
profiles = {"49643fb37a5a452da984592be8515bc1": {"username":ADMIN_USERNAME,"bio":"Hello, i am the admin profile! Did you expect a flag here? Well i'm sorry to dissapont you..."}}
user_ids = {ADMIN_USERNAME: "49643fb37a5a452da984592be8515bc1"}
issued_tokens = []
admin_request_cooldowns = {}  # username -> last request timestamp
ADMIN_REQUEST_COOLDOWN = 30   # seconds between admin bot requests per user


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        pw = request.form['password']
        if uname in users:
            flash("User already exists. Please choose a different username.", "error")
            return render_template('register.html')
        users[uname] = pw
        pid = uuid.uuid4().hex
        profiles[pid] = {"username": uname, "bio": ""}
        user_ids[uname] = pid
        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pw = request.form['password']
        if users.get(uname) == pw:
            session['username'] = uname
            return redirect(url_for('profile', profile_id=user_ids[uname]))
        flash("Invalid credentials! Please try again.", "error")
        return render_template('login.html')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/profile/<profile_id>', methods=['GET', 'POST'])
def profile(profile_id):
    if profile_id not in profiles:
        flash("Profile not found! Please try again.", "error")
        return render_template('home.html')

    profile = profiles[profile_id]

    if session.get('username') != profile['username'] and session.get('username') != ADMIN_USERNAME:
        flash("You can only view your own profile!", "error")
        return render_template('home.html')

    if request.method == 'POST':
        if profile_id == "49643fb37a5a452da984592be8515bc1":
            flash("You can't edit the admin profile!", "error")
        else:
            raw_bio = request.form.get('bio', '')
            normalized = ' '.join(str(raw_bio).split())[:500]
            profile['bio'] = Markup(normalized)

    return render_template('profile.html',
                           username=profile['username'],
                           bio=profile['bio'],
                           profile_id=profile_id)


@app.route('/guides')
def guides():
    if 'username' not in session:
        return redirect(url_for('login'))

    guide_id = request.args.get('id')

    all_guides = {
        "emmanuel": {
            "name": "Emmanuel Macron",
            "specialty": "Tours of government buildings and ministries, schools",
            "quote": "If it wasn't for France, you’d be in way deeper shit",
            "languages": "French, English",
            "img": "emmanuel.png",
        },
        "charles": {
            "name": "Charles De Gaulle",
            "specialty": "Extended island trips",
            "quote": "The better I get to know tourists, the more I find myself loving dogs.",
            "languages": "French ONLY",
            "img": "charles.png",
        },
        "jorgen": {
            "name": "Jørgen Leth",
            "specialty": "food and wine tours, bike tours, young adults",
            "quote": "Er det ikke herligt at se så mange mænd i cykelshorts?",
            "languages": "Danish, French, English, Spanish",
            "img": "jorgen.png",
        },
        "napoleon": {
            "name": "Napoleon Bonaparte",
            "specialty": "Historical tours",
            "quote": "The French complain of everything, and always.",
            "languages": "French, Italian",
            "img": "napoleon.png",
        }
    }

    if guide_id:
        guide = all_guides.get(guide_id)
        if not guide:
            flash("Guide not found! Please try again.", "error")
            return render_template('guides.html')
        return render_template("guide_detail.html", guide=guide)
    return render_template("guides.html", guides=all_guides)


@app.route('/tips')
def tips():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('tips.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash("This functionality is not yet working, we're sorry...", "error")
        return render_template('contact.html')
    return render_template('contact.html')


@app.route('/request_admin', methods=['POST'])
def request_admin():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    now = time.time()
    last_request = admin_request_cooldowns.get(username, 0)
    if now - last_request < ADMIN_REQUEST_COOLDOWN:
        remaining = int(ADMIN_REQUEST_COOLDOWN - (now - last_request))
        flash(f"Please wait {remaining}s before sending another request to the admin.", "error")
        return render_template('tips.html')

    target_url = request.form.get('target_url', '')

    if not target_url.startswith('/'):
        flash("Invalid URL! Only relative URLs allowed, and must start with a '/'", "error")
        return render_template('tips.html')

    admin_request_cooldowns[username] = now

    def notify_bot():
        full_url = f"https://{HOSTNAME_FOR_ADMIN_BOT}{target_url}"
        visit_url(full_url)

    Thread(target=notify_bot).start()

    flash("Your request has been sent to the admin, they will check it out soon!", "success")
    return render_template('tips.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('username') != ADMIN_USERNAME:
        flash("Only admins can access this page!", "error")
        return render_template('home.html')

    cleanup_tokens()
    token = uuid.uuid4().hex
    issued_tokens.append((token, time.time()))

    return render_template('admin.html', flag_token=token)


@app.route('/retrieve_flag', methods=['POST'])
def retrieve_flag():
    if session.get('username') != ADMIN_USERNAME:
        return "Unauthorized", 403

    cleanup_tokens()
    token = request.form.get('token')
    if not token:
        return "Missing token", 400

    for stored_token,_ in issued_tokens:
        if token == stored_token:
            return FLAG

    return "Invalid or expired token", 403


def visit_url(url):
    try:
        with sync_playwright() as pw:
            chromium = pw.chromium
            browser = chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--ignore-certificate-errors",
                    '--allow-third-party-cookies'
                ],
            )

            # Create a single context for all navigation so cookies persist
            context = browser.new_context(
                ignore_https_errors=True,   # accept self-signed certs
                java_script_enabled=True
            )

            # Debugging
            def on_console(msg):
                try:
                    print("Console:", msg.type, msg.text)
                except Exception:
                    pass
            context.on("page", lambda page: page.on("console", on_console))

            page = context.new_page()

            # Go to Login
            login_url = f"https://{HOSTNAME_FOR_ADMIN_BOT}/login"
            try:
                page.goto(login_url, timeout=15000)
            except PWTimeoutError:
                print(f"Timeout loading {login_url}")
            time.sleep(1)

            # Login as Admin
            try:
                page.fill('input[name="username"]', ADMIN_USERNAME)
                page.fill('input[name="password"]', ADMIN_PASSWORD)
                page.eval_on_selector("form", "form => form.submit()")
            except Exception:
                try:
                    page.press('input[name="password"]', "Enter")
                except Exception:
                    print("Could not auto-submit login form.")
            time.sleep(4)

            # Visit the user-supplied URL
            try:
                page.goto(url, timeout=30000)
            except PWTimeoutError:
                print(f"Timeout loading target page {url}")
            time.sleep(10)

            # clean up
            context.close()
            browser.close()

    except Exception as e:
        print("visit_url failure:", e)
        traceback.print_exc()
        raise


@app.after_request
def apply_cors_headers(response):
    origin = request.headers.get('Origin')
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'

    # Strict CSP: no scripts, no inline, no eval - only same-origin styles and images
    response.headers['Content-Security-Policy'] = (
        "default-src 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self'; "
        "font-src 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "script-src 'none'"
    )
    return response


@app.context_processor
def inject_user_ids():
    return dict(user_ids=user_ids)


def cleanup_tokens():
    now = time.time()
    global issued_tokens
    issued_tokens = [(t, ts) for t, ts in issued_tokens if now - ts <= FLAG_TOKEN_LIFETIME]


# No longer needed, using gunicorn to serve the app with SSL instead (see Dockerfile)
# if __name__ == '__main__':
#     app.run(
#         host='0.0.0.0',
#         port=443,
#         ssl_context=('cert.pem', 'key.pem'),
#         debug=False
#     )