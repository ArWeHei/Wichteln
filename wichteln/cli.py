import click
from flask.cli import with_appcontext

from .db import get_db
from .tokens import hash_token, new_token
from .util import format_dt


@click.command("admin-links")
@click.option(
    "--base-url",
    envvar="WICHTELN_BASE_URL",
    help="Adresse der Seite, z. B. https://name.pythonanywhere.com (oder WICHTELN_BASE_URL).",
)
@click.option(
    "--reset",
    "reset_id",
    type=int,
    metavar="ID",
    help="Neuen Verwaltungslink für das Wichteln mit dieser ID erzeugen; der alte wird ungültig.",
)
@with_appcontext
def admin_links(base_url, reset_id):
    """Zeigt die Verwaltungslinks aller Wichteln an."""
    db = get_db()
    if reset_id is not None:
        token = new_token()
        with db:
            cur = db.execute(
                "UPDATE events SET admin_token = ?, admin_token_hash = ? WHERE id = ?",
                (token, hash_token(token), reset_id),
            )
        if cur.rowcount == 0:
            raise click.ClickException(f"Kein Wichteln mit der ID {reset_id}.")
        click.echo(f"Neuer Verwaltungslink für Wichteln {reset_id} (der alte ist ungültig):")

    events = db.execute(
        "SELECT e.id, e.title, e.created_at, e.admin_token,"
        " (SELECT COUNT(*) FROM participants WHERE event_id = e.id) AS people,"
        " (SELECT COUNT(*) FROM draws WHERE event_id = e.id) AS draws"
        " FROM events e ORDER BY e.id"
    ).fetchall()
    if reset_id is not None:
        events = [e for e in events if e["id"] == reset_id]
    if not events:
        click.echo("Noch keine Wichteln angelegt.")
        return

    prefix = base_url.rstrip("/") if base_url else ""
    for e in events:
        click.echo(
            f"#{e['id']}  {e['title']}  "
            f"(angelegt {format_dt(e['created_at'])}, {e['people']} Personen, "
            f"{e['draws']} Auslosungen)"
        )
        if e["admin_token"]:
            click.echo(f"    {prefix}/admin/{e['admin_token']}")
        else:
            click.echo(
                "    Link nicht gespeichert – mit "
                f"`admin-links --reset {e['id']}` einen neuen erzeugen."
            )
    if not base_url:
        click.echo(
            "\nTipp: Mit --base-url https://deine-seite.example wird der volle Link angezeigt."
        )
