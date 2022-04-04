import functools
from quart import Quart, flash, redirect, render_template, request, session, url_for
from pathlib import Path
import validators
from dumbadmin.db import connect_db, get_db
from dumbadmin.user import get_user_from_username, register_user, register_user_sync
from dumbadmin.validate import get_browser, validate_url
from passlib.hash import pbkdf2_sha256
import re

VALID_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_]+")

app = Quart(__name__)
app.config.from_prefixed_env()
app.config.update(
    {
        "VERIFIED_DOMAIN": ["rorre.xyz", "127.0.0.1", "localhost", "10.5.0.6"],
        "DATABASE": app.root_path / "data.db",
    }
)
if not app.config.get("HOST"):
    app.config.update({"HOST": "http://127.0.0.1:8000"})


@app.before_serving
async def create_db():
    await get_browser()
    await get_db()


@app.after_serving
async def create_db_pool():
    await (await get_db()).close()
    await (await get_browser()).close()


@app.cli.command("init_db")
def init_db():
    """Create an empty database."""
    db = connect_db(app.config["DATABASE"])
    with open(Path.cwd() / "schema.sql", mode="r") as file_:
        db.cursor().executescript(file_.read())

    with open(Path.cwd() / "flag", mode="r") as f:
        username = "bob"
        password = f.read()
        register_user_sync(db, username, password)

    db.commit()


@app.route("/")
async def index():
    db = await get_db()

    app.logger.info("Fetching all jobs")
    cur = await db.execute("SELECT url, valid FROM job")
    result = await cur.fetchall()
    return await render_template("index.html", jobs=result)


@app.post("/new")
async def post():
    if not session.get("username"):
        await flash("You need to be logged in")
        return redirect(url_for("login", next="/"))

    form = await request.form
    url = form.get("url", "")

    app.logger.info("Validating URL sent")
    if not validators.url(url):
        await flash("Invalid url")
        return redirect("/")

    app.logger.info("Inserting job")
    db = await get_db()
    cur = await db.cursor()
    cur = await cur.execute("INSERT INTO job(url, valid) VALUES (?, ?)", (url, 1))
    await db.commit()

    app.logger.info("Creating background task")
    app.add_background_task(
        functools.partial(validate_url, url=url, job_id=cur.lastrowid)
    )

    await flash("Running...")
    return redirect("/")


@app.get("/admin")
async def admin():
    if not session.get("username"):
        await flash("You need to be logged in")
        return redirect(url_for("login", next="/admin"))

    if session.get("username") != "bob":
        await flash("Shoo!")
        return redirect("/")

    app.logger.info("Fetching all jobs")
    db = await get_db()
    cur = await db.execute("SELECT id, url, valid FROM job")
    result = await cur.fetchall()
    return await render_template("admin.html", jobs=result)


@app.post("/<int:job_id>/set")
async def update_post(job_id: int):
    if not session.get("username"):
        await flash("You need to be logged in")
        return redirect(url_for("login", next="/admin"))

    if session.get("username") != "bob":
        await flash("Shoo!")
        return redirect("/")

    # We are assuming everything is valid
    # Challenge note: you are not supposed to do anything with this
    form = await request.form
    db = await get_db()
    await db.execute(
        "UPDATE job SET valid = ? WHERE id = ?",
        (int(form.get("valid", "1")), job_id),
    )
    await db.commit()

    await flash("OK")
    return redirect(url_for("admin"))


@app.route("/login", methods=["GET", "POST"])
async def login():
    if request.method == "GET":
        return await render_template("login.html")

    form = await request.form
    username = form.get("username", "")
    password = form.get("password", "")
    next = request.args.get("next")

    app.logger.info("Checking for empty username/password")
    if not username or not password:
        await flash("Invalid username/password")
        return await render_template("login.html")

    app.logger.info("Fetching user from username")
    db = await get_db()
    result = await get_user_from_username(db, username)
    if not result:
        await flash("Invalid username/password")
        return await render_template("login.html")

    app.logger.info("Checking password hash")
    if not pbkdf2_sha256.verify(password, result["password"]):
        await flash("Invalid username/password")
        return await render_template("login.html")

    await flash("Logged in")
    session["username"] = username
    return redirect(next or "/")


@app.route("/register", methods=["GET", "POST"])
async def register():
    if request.method == "GET":
        return await render_template("register.html")

    form = await request.form
    username = form.get("username", "")
    password = form.get("password", "")

    app.logger.info("Checking username and password validity")
    if not username or not VALID_USERNAME_PATTERN.match(username) or not password:
        await flash("Invalid username/password")
        return await render_template("register.html")

    app.logger.info("Checking if username already taken")
    db = await get_db()
    result = await get_user_from_username(db, username)
    if result:
        await flash("Username already taken")
        return await render_template("register.html")

    app.logger.info("Registering user")
    await register_user(db, username, password)
    await flash("Registered")
    return redirect("/")
