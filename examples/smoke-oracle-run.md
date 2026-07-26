# Example run: a check that exits 0 while failing

The input is [`examples/smoke-oracle/`](smoke-oracle/): a
router with a prefix-shadowing defect, and a `smoke.sh` that
prints its real result and **always exits 0**.

That pair is the whole point. Before the repair, the check
reports two of three routes broken and returns success to
the shell:

```console
$ ./smoke.sh
  /api/v1/orders -> notfound, wanted api
  /static/app.css -> notfound, wanted static
smoke: FAIL 2 of 3 checks
$ echo $?
0
```

A loop whose success condition is the exit status is
finished before it starts, with every request misrouted.
Declaring `smoke: PASS` as the condition up front is what
makes that outcome unavailable.

**Solved in one iteration.** The agent also declined the
cheaper repair, and said why: reordering the route table
turns the check green but leaves first-match semantics under
a comment promising longest-prefix, so any later append can
silently shadow an existing route. It changed the lookup
instead.

## Run manifest

| Field         | Value                                                                   |
| ------------- | ----------------------------------------------------------------------- |
| Input         | `examples/smoke-oracle/` at repo commit `190ddd5`                       |
| Protocol      | `skill/SKILL.md`, sha256 `15c7e41186348fd2…`                            |
| Agent         | Claude Code 2.1.220                                                     |
| Invocation    | `cat prompt.txt \| claude --dangerously-skip-permissions -p`            |
| Prompt        | protocol verbatim, then the invocation line, sha256 `73e3bcae131ce9e4…` |
| Date          | 2026-07-26                                                              |
| Output sha256 | `a5cfb01253dcdc52…`                                                     |
| Edited        | No. Everything below the rule is the raw output.                        |

**One honest gap in this transcript.** Headless `-p` returns
only the final assistant message, so the per-iteration
sections the protocol's `Output shape` specifies were
streamed during the run and are not in the captured output.
What is below is the final message exactly as produced. The
observable evidence for the iteration count is the diff and
the check output, both reproduced after the rule.

Model sampling means a rerun will not be byte-identical. It
should still refuse to accept exit 0.

---

## Outcome

- **Status: solved**
- **Iterations used: 1/4** (the second run was verification)
- **Final diff:** `router.py`, one function — `route()`
  +7/−4 lines, plus the stale comment above `ROUTES`
  corrected. `smoke.sh` untouched.
- **Not validated:** nothing beyond the three smoke cases is
  covered by an automated check; the spot-check above is
  manual. `/apiary → notfound` and `/static → notfound` are
  correct for a prefix table that requires the trailing
  slash, but if the intent were segment-aware matching,
  `/static` alone would arguably belong to `static`. That's
  a spec question, not a defect against the stated checks.

Notes on the repair:

The failure here was not the routing bug — that was three
lines. It was that `./smoke.sh` exits 0 while printing
`smoke: FAIL 2 of 3 checks`. A loop that took exit status as
its condition would have declared success on iteration 1
with every request misrouted. Requiring the `smoke: PASS`
line before the first run is what made that impossible.

I fixed the defect at its source rather than reordering
`ROUTES` to put `"/"` last. Reordering also turns the smoke
check green, but it leaves the latent trap in place:
first-match semantics under a comment claiming
longest-prefix, where any future append to the table can
silently shadow existing routes. `route()` now selects the
longest matching prefix, so declaration order is no longer
load-bearing.

---

## What changed

The diff the run produced, against the committed fixture:

```diff
-# Longest-prefix routing, except the table is ordered wrongly
-# and the first entry matches every path.
+# Longest-prefix routing. Declaration order does not matter:
+# route() picks the longest matching prefix, so "/" only wins
+# when no more specific prefix matches.

 def route(path):
     """Return the handler name for a request path."""
+    best = None
     for prefix, handler in ROUTES:
         if path.startswith(prefix):
-            return handler
-    return "notfound"
+            if best is None or len(prefix) > len(best[0]):
+                best = (prefix, handler)
+    if best is None:
+        return "notfound"
+    return best[1]
```

And the check afterwards:

```console
$ ./smoke.sh
smoke: PASS 3 checks
$ echo $?
0
```

Note that the exit status is 0 in both the failing and the
passing case. It never carried any information.

## Reproducing

```sh
# Isolate the fixture, because the run edits it.
W=$(mktemp -d)
cp examples/smoke-oracle/router.py examples/smoke-oracle/smoke.sh "$W/"
chmod +x "$W/smoke.sh"

{ cat skill/SKILL.md
  printf '\n---\n\nUse the protocol above.\n\n'
  printf '/replx the smoke check passes\n\n'
  printf 'The smoke check is `./smoke.sh` in the current directory.\n'
} > "$W/prompt.txt"

cd "$W" && cat prompt.txt | claude --dangerously-skip-permissions -p
```

The prompt goes on **stdin**, not as an argument to `-p`.
`SKILL.md` opens with the `---` of its YAML frontmatter,
which the CLI otherwise parses as an unknown option and
refuses to run.
