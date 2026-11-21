"""OfficeEye - office cameras: people count, restricted area, phone use,
washroom, head down, night watch, parking, seats, fire and smoke, camera
health - with NetraAttend's attendance mounted at /attendance.

The layout (ARCHITECTURE.md):
    core/         settings, office login, cloud view, code version
    models/       stored data: records (SQLite), photos, MongoDB copy
    services/     cameras, detection and its detectors, background jobs
    controllers/  Flask Blueprints: each part's page and JSON API
    templates/    the pages (Jinja2)        static/  CSS, icons, PWA files
    server.py     start-up: python app.py in the project folder

create_app() is the application factory: it builds the Flask app from the
parts above. Nothing is imported here at package level, so importing one
module (tools/ do) does not load the rest.
"""


def create_app():
    """The Flask app with every controller (Blueprint) and the login of this
    mode (office PC or cloud view) in front of them."""
    from flask import Flask

    from officeeye.controllers import blueprints
    from officeeye.core import access, cloud

    app = Flask(__name__)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    cloud.install(app)
    if not cloud.CLOUD:
        access.install(app)             # the office PC's login: view, and edit (Settings -> Login)
    for bp in blueprints():
        app.register_blueprint(bp)
    return app
