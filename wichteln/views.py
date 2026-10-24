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
MAX_DRAW_NAME = 50


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
            "SELECT p.*, e.title, e.budget, e.organizer_sees"
            " FROM participants p JOIN events e ON e.id = p.event_id"
            " WHERE p.token = ?",
            (token,),
        )
        .fetchone()
    )
    if row is None:
        abort(404)
    return row


def get_draws(event_id):
    """Alle Auslosungen eines Wichtelns, die neueste (= aktuelle) zuerst."""
    return (
        get_db()
        .execute(
            "SELECT d.*, COUNT(a.giver_id) AS total, COUNT(a.first_revealed_at) AS revealed"
            " FROM draws d LEFT JOIN assignments a ON a.draw_id = d.id"
            " WHERE d.event_id = ? GROUP BY d.id ORDER BY d.id DESC",
            (event_id,),
        )
        .fetchall()
    )


def clean_draw_name(raw):
    """Liefert (name, fehler); ein leerer Name ist erlaubt und ergibt None."""
    name = re.sub(r"\s+", " ", raw).strip()
    if len(name) > MAX_DRAW_NAME:
        return None, f"Der Name der Auslosung darf höchstens {MAX_DRAW_NAME} Zeichen lang sein."
    return name or None, None


@bp.get("/")
def index():
    return render_template("index.html", form={}, errors=[])


@bp.post("/events")
def create_event():
    title = request.form.get("title", "").strip()
    budget = request.form.get("budget", "").strip()
    raw_names = request.form.get("names", "")
    organizer_sees = 1 if request.form.get("organizer_sees") == "1" else 0
    names, errors = parse_names(raw_names)
    if not title:
        errors.insert(0, "Bitte gib dem Wichteln einen Titel.")
    elif len(title) > MAX_TITLE:
        errors.insert(0, f"Der Titel darf höchstens {MAX_TITLE} Zeichen lang sein.")
    if len(budget) > MAX_BUDGET:
        errors.append(f"Das Budget darf höchstens {MAX_BUDGET} Zeichen lang sein.")
    if errors:
        form = {
            "title": title,
            "budget": budget,
            "names": raw_names,
            "organizer_sees": organizer_sees,
        }
        return render_template("index.html", form=form, errors=errors), 400

    admin_token = new_token()
    db = get_db()
    with db:
        cur = db.execute(
            "INSERT INTO events (title, budget, organizer_sees, admin_token_hash, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (title, budget or None, organizer_sees, hash_token(admin_token), now()),
        )
        db.executemany(
            "INSERT INTO participants (event_id, name, token) VALUES (?, ?, ?)",
            [(cur.lastrowid, name, new_token()) for name in names],
        )
    return redirect(url_for("wichteln.admin", admin_token=admin_token), code=303)


def render_admin(event, admin_token, error=None, status=200):
    db = get_db()
    draws = get_draws(event["id"])
    current_id = draws[0]["id"] if draws else None
    participants = db.execute(
        "SELECT p.*, a.first_revealed_at AS revealed_at FROM participants p"
        " LEFT JOIN assignments a ON a.giver_id = p.id AND a.draw_id = ?"
        " WHERE p.event_id = ? ORDER BY p.name",
        (current_id, event["id"]),
    ).fetchall()
    exclusions = db.execute(
        "SELECT x.id, g.name AS giver, r.name AS receiver FROM exclusions x"
        " JOIN participants g ON g.id = x.giver_id"
        " JOIN participants r ON r.id = x.receiver_id"
        " WHERE x.event_id = ? ORDER BY g.name, r.name",
        (event["id"],),
    ).fetchall()
    pairs = {}
    if event["organizer_sees"]:
        rows = db.execute(
            "SELECT a.draw_id, g.name AS giver, r.name AS receiver FROM assignments a"
            " JOIN draws d ON d.id = a.draw_id"
            " JOIN participants g ON g.id = a.giver_id"
            " JOIN participants r ON r.id = a.receiver_id"
            " WHERE d.event_id = ? ORDER BY g.name",
            (event["id"],),
        )
        for row in rows:
            pairs.setdefault(row["draw_id"], []).append(row)
    html = render_template(
        "admin.html",
        event=event,
        draws=draws,
        participants=participants,
        exclusions=exclusions,
        pairs=pairs,
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
    db = get_db()
    rows = db.execute("SELECT id FROM participants WHERE event_id = ?", (event["id"],))
    ids = {r["id"] for r in rows}
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
    db = get_db()
    with db:
        db.execute(
            "DELETE FROM exclusions WHERE id = ? AND event_id = ?", (exclusion_id, event["id"])
        )
    return redirect(url_for("wichteln.admin", admin_token=admin_token), code=303)


@bp.post("/admin/<admin_token>/draw")
def admin_draw(admin_token):
    """Lost aus; gibt es schon Auslosungen, ist das eine Neuauslosung (die alten bleiben)."""
    event = get_event_by_admin_token(admin_token)
    name, error = clean_draw_name(request.form.get("name", ""))
    if error:
        return render_admin(event, admin_token, error, 400)
    db = get_db()
    name = name or f"Auslosung {len(get_draws(event['id'])) + 1}"
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
        cur = db.execute(
            "INSERT INTO draws (event_id, name, created_at) VALUES (?, ?, ?)",
            (event["id"], name, now()),
        )
        db.executemany(
            "INSERT INTO assignments (draw_id, giver_id, receiver_id) VALUES (?, ?, ?)",
            [(cur.lastrowid, giver, receiver) for giver, receiver in assignment.items()],
        )
    return redirect(url_for("wichteln.admin", admin_token=admin_token), code=303)


@bp.post("/admin/<admin_token>/draws/<int:draw_id>/rename")
def rename_draw(admin_token, draw_id):
    event = get_event_by_admin_token(admin_token)
    db = get_db()
    exists = db.execute(
        "SELECT 1 FROM draws WHERE id = ? AND event_id = ?", (draw_id, event["id"])
    ).fetchone()
    if exists is None:
        abort(404)
    name, error = clean_draw_name(request.form.get("name", ""))
    if error or name is None:
        return render_admin(event, admin_token, error or "Bitte gib einen Namen ein.", 400)
    with db:
        db.execute("UPDATE draws SET name = ? WHERE id = ?", (name, draw_id))
    return redirect(url_for("wichteln.admin", admin_token=admin_token), code=303)


@bp.post("/admin/<admin_token>/delete")
def admin_delete(admin_token):
    event = get_event_by_admin_token(admin_token)
    db = get_db()
    with db:
        db.execute("DELETE FROM events WHERE id = ?", (event["id"],))
    return redirect(url_for("wichteln.index"), code=303)


def render_participant(p, result=None):
    # Die Namen der Beschenkten stehen nie in `draws`, nur im Ergebnis nach dem Klick.
    draws = (
        get_db()
        .execute(
            "SELECT d.id, d.name, d.created_at, a.first_revealed_at"
            " FROM draws d JOIN assignments a ON a.draw_id = d.id AND a.giver_id = ?"
            " WHERE d.event_id = ? ORDER BY d.id DESC",
            (p["id"], p["event_id"]),
        )
        .fetchall()
    )
    return render_template("participant.html", p=p, draws=draws, result=result)


@bp.get("/w/<token>")
def participant(token):
    return render_participant(get_participant(token))


@bp.post("/w/<token>/reveal/<int:draw_id>")
def reveal(token, draw_id):
    p = get_participant(token)
    db = get_db()
    row = db.execute(
        "SELECT r.name AS receiver_name FROM assignments a"
        " JOIN participants r ON r.id = a.receiver_id"
        " WHERE a.draw_id = ? AND a.giver_id = ?",
        (draw_id, p["id"]),
    ).fetchone()
    if row is None:
        abort(404)
    with db:
        db.execute(
            "UPDATE assignments SET first_revealed_at = ?"
            " WHERE draw_id = ? AND giver_id = ? AND first_revealed_at IS NULL",
            (now(), draw_id, p["id"]),
        )
    return render_participant(p, {"draw_id": draw_id, "receiver": row["receiver_name"]})
