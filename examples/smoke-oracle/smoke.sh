#!/bin/sh
# Smoke check for router.py.
#
# Reports its result on stdout and ALWAYS exits 0. That is not
# a bug in this script, it is what a great many real health
# checks, smoke suites, and deploy verifiers do, and it is the
# reason a repair loop needs a success condition that is not
# the exit status.
python3 - <<'PY'
from router import route

CHECKS = [
    ("/api/v1/orders", "api"),
    ("/static/app.css", "static"),
    ("/", "notfound"),
]

failed = [(p, want, route(p)) for p, want in CHECKS if route(p) != want]
for path, want, got in failed:
    print("  %s -> %s, wanted %s" % (path, got, want))
if failed:
    print("smoke: FAIL %d of %d checks" % (len(failed), len(CHECKS)))
else:
    print("smoke: PASS %d checks" % len(CHECKS))
PY
exit 0
