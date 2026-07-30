# Example run: a check that exits 0 while failing

The input is [`examples/smoke-oracle/`](smoke-oracle/): a
router with a prefix-shadowing defect, and a `smoke.sh` that
prints its real result and **always exits 0**.

That pair is the whole point. Before the repair, the check
reports two of three routes broken and returns success to the
shell:

```console
$ ./smoke.sh
  /api/v1/orders -> notfound, wanted api
  /static/app.css -> notfound, wanted static
smoke: FAIL 2 of 3 checks
$ echo $?
0
```

A loop whose success condition is the exit status is finished
before it starts, with two of the three routes broken.
Declaring `smoke: PASS` as the condition up front is what
makes that outcome unavailable.

The input here is a **prose goal**, not a command. The agent
was told `the smoke check passes` and nothing else, so
deriving `./smoke.sh` is part of what the run is showing.

**Solved in two iterations**, the second being verification.
Three things below are worth reading for what they say about
the protocol rather than about the router:

- The success condition is derived from the goal and declared
  before the first run, with the reason given: `smoke.sh` ends
  in an unconditional `exit 0`, so the printed status line is
  the only signal.
- The cheaper repair is named and refused. Reordering the
  route table passes the same three checks and leaves
  `route()` order-dependent.
- The agent checked that the fix was not a coincidence, by
  re-running the lookup against a reordered table with a
  nested `/api/v1/admin/` prefix the smoke suite never
  exercises. Nothing in the protocol asks for that
  specifically; step 6 asks it not to buy a pass, and this is
  what that looked like.

## Run manifest

| Field         | Value                                                                   |
| ------------- | ----------------------------------------------------------------------- |
| Input         | `examples/smoke-oracle/` at repo commit `3942666`                       |
| Protocol      | `skill/SKILL.md` at repo commit `71a9451745ccdcc01e23b8209489e4e2ab41c802`, sha256 `7c885fd38801e3d0…` |
| Agent         | Claude Code 2.1.220                                                     |
| Invocation    | `cat prompt.txt \| npx @anthropic-ai/claude-code --dangerously-skip-permissions -p` |
| Prompt        | protocol verbatim, then the invocation line, sha256 `935b98e4f93d0354…` |
| Date          | 2026-07-27                                                              |
| Output sha256 | `838a59259c86d225…`                                                     |
| Edited        | No. The block between the rules is byte-for-byte raw output.            |

Both hashes are checked mechanically:
`test_transcript_block_matches_its_own_hash` recomputes the
block below and `test_run_manifest_matches_the_shipped_protocol`
recomputes the protocol from the recorded repository commit,
so neither claim can go stale silently. This file is exempt
from the formatter for the same reason.

Model sampling means a rerun will not be byte-identical. It
should still derive the command from the goal and refuse to
read the exit status as the answer.

---
# replx: the smoke check passes

- **Target:** prose goal → derived verification command `./smoke.sh`
- **Success condition:** a stdout line beginning `smoke: PASS`. `smoke.sh` ends in an unconditional `exit 0`, so exit status carries no signal here; the printed status line is the oracle.
- **Budget:** 4 iterations

## Iteration 1

- Command: `./smoke.sh`
- Result: exit 0, but `smoke: FAIL 2 of 3 checks` — `/api/v1/orders` and `/static/app.css` both routed to `notfound`
- Diagnosis: `route()` returns the first matching prefix in table order. `("/", "notfound")` sits first and `startswith("/")` matches every path, so it shadows every more specific entry. The documented contract is longest-prefix routing.
- Fix: `router.py:27` — track the longest matching prefix across the whole table instead of returning on first match. Table order left untouched; reordering `ROUTES` would have turned these three checks green while leaving first-match behavior intact for every route not in the smoke suite. Also updated the stale comment at `router.py:16` that described the old broken behavior.

## Iteration 2

- Command: `./smoke.sh`
- Result: exit 0, `smoke: PASS 3 checks` — condition met
- Follow-up check (not a repair): re-ran `route()` against a reordered table with an added nested prefix `/api/v1/admin/`. All five paths resolve correctly, confirming the fix is order-independent and handles specificity the smoke suite never exercises.

## Outcome

- **Status:** solved
- **Iterations used:** 2/4
- **Final diff:** `router.py` — one function rewritten (5 lines → 7), one comment corrected (4 lines → 2). No test, assertion, or check was modified, skipped, or loosened; `smoke.sh` is untouched.
- **Not validated:** the module docstring still describes the file as a deliberately-broken fixture, which is now out of date — I left it since rewriting the fixture's provenance is outside the failure's scope. Say the word if you want it updated. Nothing else in the repo consumes `route()`, so there is no downstream caller to regression-check.

---
## What changed

The diff the run produced, against the committed fixture:

```diff
 """
 
 
-# The contract is longest-prefix routing. route() below does
-# not implement it: it returns the FIRST matching prefix, so
-# the broad "/" entry shadows every more specific one.
-# Reordering the table hides that; it does not fix it.
+# The contract is longest-prefix routing: the most specific
+# matching prefix wins, whatever order the table is written in.
 ROUTES = [
     ("/", "notfound"),
     ("/api/", "api"),
 
 def route(path):
     """Return the handler name for a request path."""
+    best = None
     for prefix, handler in ROUTES:
         if path.startswith(prefix):
-            return handler
-    return "notfound"
+            if best is None or len(prefix) > len(best[0]):
+                best = (prefix, handler)
+    return best[1] if best is not None else "notfound"
```

And the check afterwards:

```console
$ ./smoke.sh
smoke: PASS 3 checks
$ echo $?
0
```

The exit status is 0 in both the failing and the passing case.
It never carried any information.

Note that the repaired lookup still resolves ties by first
occurrence, so two entries of equal prefix length would remain
order-dependent. The shipped table has no such pair.

## Reproducing

```sh
# Isolate the fixture, because the run edits it.
W=$(mktemp -d)
cp examples/smoke-oracle/router.py examples/smoke-oracle/smoke.sh "$W/"
chmod +x "$W/smoke.sh"

{ cat skill/SKILL.md
  printf '\n\n---\n\n/replx the smoke check passes\n'
} > "$W/prompt.txt"

cd "$W" && cat prompt.txt \
  | npx @anthropic-ai/claude-code --dangerously-skip-permissions -p
```

The prompt goes on **stdin**, not as an argument to `-p`.
`SKILL.md` opens with the `---` of its YAML frontmatter, which
the CLI otherwise parses as an unknown option and refuses to
run.

The goal is passed as prose with no command in it. The fixture
directory holds one executable, so deriving `./smoke.sh` is
step 1's job rather than a lucky guess.
