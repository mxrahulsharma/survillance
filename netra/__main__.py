"""NetraAttend on its own, as before: camera, face matching and the website on
port 5000 (ROLE "all"), or the website only with NETRA_ROLE=web.

    py -3.12 -m netra          (from the OfficeEye folder)
"""
from . import load_env

load_env()

from .app import main  # noqa: E402 - after the .env settings are in the environment

main()
