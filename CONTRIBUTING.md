# Contributing

`replx` is one Markdown file, one harness, and one case.
That makes contributing cheap and makes a careless change
easy to miss. Here is what helps.

## The most useful contribution

**A bad success the harness scored as `solved`.** A patch
that makes the target command pass without fixing the
defect, which the held-out checks and the semantic guard
both let through, is the single most valuable thing anyone
can send. It is a hole in the oracle, and the oracle is the
product.

Open an issue with the case, the patch, and what the checks
should have caught. Label it `oracle-gap`.

Three other kinds are close behind:

- **A new case.** One case is a demonstration, not a
  benchmark. See the requirements below.
- **A run.** Any model, any endpoint, including a
  `bad_success` result. `eval/RESULTS.md` has no rows yet.
- **A loop that talked itself into a weak repair.** If the
  protocol's step 6 failed to prevent one of the repairs it
  names, that is a protocol bug. Include the transcript.

## Requirements for a new case

A case is only worth adding if it discriminates. Verify all
four behaviours by hand before opening the pull request, and
put the results in the description:

| Applied patch           | Visible command | Held-out checks   |
| ----------------------- | --------------- | ----------------- |
| none, defect seeded     | fails           | not reached       |
| the real fix            | passes          | pass              |
| a plausible shortcut    | passes          | **fail**          |
| the visible test gutted | passes          | fail, guard fires |

If a shortcut you can think of passes the held-out checks,
the case will score a reward hack as a solve, which is worse
than having no case at all.

Two mechanical rules, both of which come from real mistakes
made while building this:

- **Generate patches with git, not by hand.** A wrong hunk
  line count applies silently and truncates the file. The
  result is an import error during verification that looks
  exactly like a failed check, so the case appears to work
  while measuring nothing.
- **Never let the answer reach the sandbox.** Do not list a
  file in `context_files` that contains the fix, and do not
  put the expected value in `description`. The case
  directory is stripped from the sandbox, but
  `context_files` is pasted straight into the prompt.

Cases must run on a clean clone with only `python3`. No
third-party packages, no build tools.

## Changing the protocol

`skill/SKILL.md` is the product. A change to it should come
with the before and after run output that motivated it, on
the same input. "This wording seems better" is not
reviewable. "This wording is what stopped the loop from
deleting the test" is.

Six properties are load-bearing. Do not remove them without
making the case explicitly:

1. **The success condition is declared before the first
   iteration**, so the loop cannot later redefine success as
   something it has already achieved.
2. **A condition can be semantic, not only mechanical.**
   This is the whole thesis. `no build warnings` is a valid
   target with no exit status behind it, and a check that
   prints `FAIL` and exits 0 must not end the run.
3. **One run per iteration, never a shell loop.** No
   `until`, `while`, or `for` wrapping the command. Each
   attempt is a fresh diagnosis, not a retry.
4. **The named repairs do not count**, and the list stays
   explicit. A loop that has not named them will find them.
5. **An honest unsolved outranks a green command with a
   weakened test**, and an exhausted budget is never
   reported as partial success.
6. **The failing output is evidence, not instruction.** A
   comment or error message telling the agent to delete the
   test does not authorize it.

## Changing the harness

Six tests are load-bearing in the same sense. If any of them
stops passing, claims in the README become false:

- `test_held_out_checks_reject_shortcut_patch`
- `test_repair_prompt_never_reveals_the_oracle`
- `test_case_metadata_is_stripped_from_the_worktree`
- `test_sandbox_has_no_history_to_read_the_answer_from`
- `test_shipped_case_runs_end_to_end`
- `test_run_manifest_matches_the_shipped_protocol`

The second one is the one to be most careful around.
Anything that adds detail to what the model is told after a
failed check is a regression, even when it would obviously
help the model. Helping the model is not the goal; measuring
it is.

Run the suite before opening a pull request:

```sh
python3 -m unittest discover -s eval -q
```

## Style

Prose wraps at 60 columns.

Do not use dashes as punctuation. Use a comma, a colon,
parentheses, or a new sentence. Hyphens inside compound
words are fine. Committed transcripts are exempt, because
they are raw output and editing them would falsify the
manifest.

Keep the protocol imperative and free of hedging. It is read
by agents, and "consider possibly checking" produces the
loop you would expect.

## Good first issues

Issues labelled `good first issue` are usually a new case in
a language or defect class not represented yet. The existing
case is an off-by-one in Python. A compile error, a flaky
test, a bad migration, or a lint failure would each exercise
a different part of the protocol.
