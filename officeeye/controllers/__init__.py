"""Controllers (the C of MVC): Flask Blueprints, one file per part of the app.
Each one has that part's page and the JSON API the page talks to; it reads
the request, asks the services / models and answers. The work itself is in
services/, the stored data in models/, the HTML in templates/."""


def blueprints():
    """Every controller's Blueprint, for create_app()."""
    from officeeye.controllers import (attendance, cameras, dashboard, fire, health, live, night, parking,
                                       phone, push, records, restricted, running_time, search, seats,
                                       settings, sleeping, washroom)
    return [m.bp for m in (dashboard, live, search, restricted, records, running_time, phone, sleeping,
                           night, parking, washroom, seats, health, fire, cameras, settings, push,
                           attendance)]
