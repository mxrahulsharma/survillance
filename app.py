"""OfficeEye - start it here:  py -3.12 app.py  (run.bat, the Windows Startup
script and the Docker image all run this file).

The app itself is the officeeye/ package - see ARCHITECTURE.md for the
layout: core, models, services, controllers, templates, static. NetraAttend
(attendance) is the netra/ package, mounted at /attendance.
"""

from officeeye.server import main

if __name__ == "__main__":
    main()
