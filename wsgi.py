"""WSGI-Einstiegspunkt für PythonAnywhere und gunicorn (`wsgi:application`)."""

from wichteln import create_app

application = create_app()
