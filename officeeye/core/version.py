"""A short fingerprint of the app's own files. It changes when new code is
running (not on a plain restart); open pages - the installed app on the PC
and on phones too - see it in /api/status and reload themselves."""

import hashlib
import os

from officeeye.core import config

PACKAGE = os.path.join(config.BASE_DIR, "officeeye")


def _code_version():
    h = hashlib.sha1()
    files = [os.path.join(config.BASE_DIR, "app.py")]
    ends = (".py", ".html", ".js", ".css", ".webmanifest")
    for folder, _, names in sorted(os.walk(PACKAGE)):
        files += [os.path.join(folder, n) for n in sorted(names) if n.endswith(ends)]
    for path in files:
        try:
            with open(path, "rb") as fh:
                h.update(os.path.relpath(path, config.BASE_DIR).replace("\\", "/").encode())
                h.update(fh.read())
        except OSError:
            pass
    return h.hexdigest()[:12]


APP_VERSION = _code_version()
