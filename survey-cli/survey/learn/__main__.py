"""Entry point: ``python -m survey.learn ...``

Issue SR-55 fordert auch ``python -m survey learn ...``. Das geht NUR wenn
``survey/`` ein eigenes ``__main__.py`` mit Subcommand-Routing hat. Da das
Top-Level-Package aktuell noch keinen einheitlichen CLI-Dispatcher hat,
liefern wir hier ``survey.learn`` als eigenstaendigen Einstieg. Wenn
das Top-Level dispatcher kommt, kann er einfach an ``survey.learn.cli.main``
delegieren.
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
