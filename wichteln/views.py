import re
from datetime import datetime, timezone

from flask import Blueprint, abort, redirect, render_template, request, url_for

from .db import get_db
from .draw import NoValidAssignment, draw
from .tokens import hash_token, new_token

bp = Blueprint("wichteln", __name__)

MIN_PARTICIPANTS = 3
MAX_PARTICIPANTS = 100
MAX_NAME = 50
MAX_TITLE = 100
MAX_BUDGET = 50


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_names(raw):
    """Zerlegt die Eingabe in saubere, eindeutige Namen; liefert (namen, fehler)."""
    names, seen, errors = [], set(), []
    for line in raw.splitlines():
        name = re.sub(r"\s+", " ", line).strip()
        if not name:
            continue
        if len(name) > MAX_NAME:
            errors.append(f"„{name[:20]}…“ ist länger als {MAX_NAME} Zeichen.")
        elif name.casefold() in seen:
            errors.append(f"„{name}“ kommt doppelt vor (z. B. „{name} M.“ und „{name} K.“).")
        else:
            seen.add(name.casefold())
            names.append(name)
    if len(names) < MIN_PARTICIPANTS:
        errors.append(f"Es braucht mindestens {MIN_PARTICIPANTS} Personen.")
    if len(names) > MAX_PARTICIPANTS:
        errors.append(f"Es sind höchstens {MAX_PARTICIPANTS} Personen erlaubt.")
    return names, errors


def get_event_by_admin_token(token):
    row = (
        get_db()
        .execute("SELECT * FROM events WHERE admin_token_hash = ?", (hash_token(token),))
        .fetchone()
    )
    if row is None:
        abort(404)
    return row


def get_participant(token):
    row = (
        get_db()
        .execute(
            "SELECT p.*, e.title, e.budget, e.status,"
            " r.name AS receiver_name"
            " FROM participants p JOIN events e ON e.id = p.event_id"
            " LEFT JOIN participants r ON r.id = p.receiver_id"
            " WHERE p.token = ?",
            (token,),
        )
        .fetchone()
    )
    if row is None:
        abort(404)
    return row


@bp.get("/")
def index():
    return render_template("index.html", form={}, errors=[])


@bp.post("/events")
def create_event():
    title = request.form.get("title", "").strip()
    budget = request.form.get("budget", "").strip()
    raw_names = request.form.get("names", "")
    names, errors = parse_names(raw_names)
    if not title:
        errors.insert(0, "Bitte gib dem Wichteln einen Titel.")
    elif len(title) > MAX_TITLE:
        errors.insert(0, f"Der Titel darf höchstens {MAX_TITLE} Zeichen lang sein.")
    if len(budget) > MAX_BUDGET:
        errors.append(f"Das Budget darf höchstens {MAX_BUDGET} Zeichen lang sein.")
    if errors:
        form = {"title": title, "budget": budget, "names": raw_names}
        return render_template("index.html", form=form, errors=errors), 400

    admin_token = new_token()
    db = get_db()
    with db:
        cur = db.execute(
            "INSERT INTO events (title, budget, admin_token_hash, created_at) VALUES (?, ?, ?, ?)",
            (title, budget or None, hash_token(admin_token), now()),
        )
        db.executemany(
            "INSERT INTO participants (event_id, name, token) VALUES (?, ?, ?)",
            [(cur.lastrowid, name, new_token()) for name in names],
        )
    return redirect(url_for("wichteln.admin", admin_token=admin_token), code=303)


def render_admin(event, admin_token, error=None, status=200):
    db = get_db()
    participants = db.execute(
        "SELECT * FROM participants WHERE event_id = ? ORDER BY name", (event["id"],)
    ).fetchall()
    exclusions = db.execute(
        "SELECT x.id, g.name AS giver, r.name AS receiver FROM exclusions x"
        " JOIN participants g ON g.id = x.giver_id"
        " JOIN participants r ON r.id = x.receiver_id"
        " WHERE x.event_id = ? ORDER BY g.name, r.name",
        (event["id"],),
    ).fetchall()
    html = render_template(
        "admin.html",
        event=event,
        participants=participants,
        exclusions=exclusions,
        admin_token=admin_token,
        error=error,
    )
    return html, status


@bp.get("/admin/<admin_token>")
def admin(admin_token):
    return render_admin(get_event_by_admin_token(admin_token), admin_token)


@bp.post("/admin/<admin_token>/exclusions")
def add_exclusion(admin_token):
    event = get_event_by_admin_token(admin_token)
    if event["status"] != "draft":
        abort(409)
    db = get_db()
    ids = {
        r["id"]
        for r in db.execute("SELECT id FROM participants WHERE event_id = ?", (event["id"],))
    }
    try:
        giver = int(request.form.get("giver", ""))
        receiver = int(request.form.get("receiver", ""))
    except ValueError:
        return render_admin(event, admin_token, "Bitte zwei Personen auswählen.", 400)
    if giver not in ids or receiver not in ids:
        abort(400)
    if giver == receiver:
        return render_admin(event, admin_token, "Bitte zwei verschiedene Personen wählen.", 400)
    pairs = [(giver, receiver)]
    if request.form.get("mutual"):
        pairs.append((receiver, giver))
    with db:
        db.executemany(
            "INSERT OR IGNORE INTO exclusions (event_id, giver_id, receiver_id) VALUES (?, ?, ?)",
            [(event["id"], g, r) for g, r in pairs],
        )
    return redirect(url_for("wichteln.admin", admin_token=admin_token), code=303)


@bp.post("/admin/<admin_token>/exclusions/<int:exclusion_id>/delete")
def delete_exclusion(admin_token, exclusion_id):
    event = get_event_by_admin_token(admin_token)
    if event["status"] != "draft":
        abort(409)
    db = get_db()
    with db:
        db.execute(
            "DELETE FROM exclusions WHERE id = ? AND event_id = ?", (exclusion_id, event["id"])
        )
    return redirect(url_for("wichteln.admin", admin_token=admin_token), code=303)


@bp.post("/admin/<admin_token>/draw")
def admin_draw(admin_token):
    event = get_event_by_admin_token(admin_token)
    if event["status"] != "draft":
        abort(409)
    db = get_db()
    ids = [
        r["id"]
        for r in db.execute("SELECT id FROM participants WHERE event_id = ?", (event["id"],))
    ]
    exclusions = {
        (r["giver_id"], r["receiver_id"])
        for r in db.execute(
            "SELECT giver_id, receiver_id FROM exclusions WHERE event_id = ?", (event["id"],)
        )
    }
    try:
        assignment = draw(ids, exclusions)
    except NoValidAssignment:
        return render_admin(
            event,
            admin_token,
            "Mit diesen Ausschlüssen ist keine Auslosung möglich. Bitte entferne einige.",
            409,
        )
    with db:
        db.executemany(
            "UPDATE participants SET receiver_id = ? WHERE id = ?",
            [(receiver, giver) for giver, receiver in assignment.items()],
        )
        db.execute(
            "UPDATE events SET status = 'drawn', drawn_at = ? WHERE id = ?", (now(), event["id"])
        )
    return redirect(url_for("wichteln.admin", admin_token=admin_token), code=303)


@bp.post("/admin/<admin_token>/delete")
def admin_delete(admin_token):
    event = get_event_by_admin_token(admin_token)
    db = get_db()
    with db:
        db.execute("DELETE FROM events WHERE id = ?", (event["id"],))
    return redirect(url_for("wichteln.index"), code=303)


@bp.get("/w/<token>")
def participant(token):
    p = get_participant(token)
    return render_template("participant.html", p=p, revealed=False)


@bp.post("/w/<token>/reveal")
def reveal(token):
    p = get_participant(token)
    if p["status"] != "drawn" or p["receiver_name"] is None:
        abort(409)
    if p["first_revealed_at"] is None:
        db = get_db()
        with db:
            db.execute(
                "UPDATE participants SET first_revealed_at = ?"
                " WHERE id = ? AND first_revealed_at IS NULL",
                (now(), p["id"]),
            )
    return render_template("participant.html", p=p, revealed=True)
