import os
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import cli, db, views
from .util import format_dt


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config["DATABASE"] = os.environ.get(
        "WICHTELN_DB", os.path.join(app.instance_path, "wichteln.db")
    )
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    app.config.update(config or {})

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    db.init_db(app.config["DATABASE"])

    # Hinter Reverse-Proxy (PythonAnywhere, Caddy) das richtige Schema/den Host übernehmen.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.teardown_appcontext(db.close_db)
    app.jinja_env.filters["dt"] = format_dt
    app.register_blueprint(views.bp)
    app.cli.add_command(cli.admin_links)

    @app.after_request
    def secure_headers(resp):
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'self'; script-src 'self'; "
            "img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
        )
        if not resp.headers.get("Cache-Control"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app
