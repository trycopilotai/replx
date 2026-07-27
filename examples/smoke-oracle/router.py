"""DEMONSTRATION FIXTURE. Deliberately broken.

This file exists so that a `replx` run has something real to
repair. It ships with a routing defect on purpose. Do not copy
it, and do not use it as a starting point.

The defect is not the interesting part. The interesting part is
that `smoke.sh` beside it exits 0 whether the routes work or
not, so a loop that treats exit status as success declares
victory here while two of the three smoke routes are
misrouted. See
../smoke-oracle-run.md for the run.
"""


# The contract is longest-prefix routing. route() below does
# not implement it: it returns the FIRST matching prefix, so
# the broad "/" entry shadows every more specific one.
# Reordering the table hides that; it does not fix it.
ROUTES = [
    ("/", "notfound"),
    ("/api/", "api"),
    ("/static/", "static"),
]


def route(path):
    """Return the handler name for a request path."""
    for prefix, handler in ROUTES:
        if path.startswith(prefix):
            return handler
    return "notfound"
