"""Forgot the login (Settings -> Login)? This removes it - then restart
OfficeEye right away, and set a new one in Settings -> Login.

    py -3.12 tools/reset_login.py
"""

import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "config.json")


def main():
    with open(PATH, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if cfg.pop("access", None) is None:
        print("No login is set - nothing to do.")
        return
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    os.replace(tmp, PATH)
    print("The login is removed. Restart OfficeEye now; then set a new one in Settings -> Login.")


if __name__ == "__main__":
    main()
