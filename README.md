<p align="center">
  <img src="assets/logo.svg" alt="" width="84" height="84">
</p>

<h1 align="center">replx</h1>

<p align="center"><strong>A semantic repair loop that actually fixes code.</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license">
  <img src="https://img.shields.io/badge/protocol-no%20dependencies-brightgreen.svg" alt="The protocol has no dependencies">
  <img src="https://img.shields.io/badge/protocol-one%20markdown%20file-blue.svg" alt="The protocol is one Markdown file">
  <img src="https://img.shields.io/badge/success-mechanical%20or%20semantic-8957e5.svg" alt="Success conditions can be mechanical or semantic">
</p>

`replx` drives a failing command to green in bounded
iterations, one attempt per iteration, each with a fresh
diagnosis. That part is not new.

What it adds is that the success condition can be stated in
prose. Both of these are valid input:

```text
/replx make test
/replx make test passes and prints no build warnings
```

The first is mechanical, and the shell exit status decides
it. The second is semantic, and no exit status can decide
it, because a build that warns still exits 0. `replx` fixes
the condition before the first iteration and holds the loop
to it.

That is the difference from an exit-status loop. A "Ralph
Wiggum" loop can only ask whether the command came back
green. It cannot ask whether the command was telling the
truth, and it cannot express a goal the command does not
already measure.

It also names the repairs that are not allowed to count.
Deleting the failing test makes any command pass, so the
protocol rules that class out and the harness in `eval/`
scores whether an agent took the shortcut anyway.

The protocol is one Markdown file with no dependencies and
no runtime: there is nothing to install beyond the agent you
already use. The evaluation harness in `eval/` is separate
and needs `python3` and `git`.

## The problem it exists for

This smoke check reports two broken routes and returns
success to the shell:

```console
$ ./smoke.sh
  /api/v1/orders -> notfound, wanted api
  /static/app.css -> notfound, wanted static
smoke: FAIL 2 of 3 checks
$ echo $?
0
```

Any loop whose condition is `$? == 0` is already finished,
with two of the three routes broken. The fixture is
deliberately minimal, but the shape is not invented: health
checks, smoke suites, and deploy verifiers can report a
failure and still exit 0, because they are written to report
rather than to gate.

The other half runs the opposite way. When a command does
fail honestly, one of the cheapest repairs available is to
delete the assertion. Both outcomes look like success.

## A real run

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/demo-poster.png">
  <img src="assets/demo.gif" alt="replx repairing a router whose smoke check exits 0 while reporting two failures, then verifying the fix">
</picture>

A condensed rendering of the committed transcript, not a
screen capture. Every value it shows is parsed from that
transcript by `assets/build.py`, and a test fails if the two
disagree. The connective lines between them are written for
the animation. The full text is in
[`examples/smoke-oracle-run.md`](examples/smoke-oracle-run.md),
which carries the hashes.

The input was the prose goal `the smoke check passes`, with
no command in it. Deriving `./smoke.sh` and deciding that
the printed status line is the oracle are both part of the
run.

Two iterations, the second being verification. The agent
declined the cheaper repair and said why: reordering the
route table turns these three checks green while leaving
first-match behaviour intact for every route the smoke suite
does not cover. It changed the lookup instead, and left the
table in its original order.

Transcript, input, and run manifest:
[`examples/smoke-oracle-run.md`](examples/smoke-oracle-run.md).

## Use it

Paste [`skill/SKILL.md`](skill/SKILL.md) into your agent as
the instructions, then give it a failing command. That is
the whole contract.

### Claude Code

Install the tagged skill package:

```sh
set -eu
install_parent="$HOME/.claude/skills"
install_target="$install_parent/replx"
mkdir -p "$install_parent"
install_tmp="$(mktemp -d "$install_parent/.replx.XXXXXX")"
rollback_install() {
  if [ ! -e "$install_target" ]; then
    if [ -e "$install_tmp/previous" ]; then
      mv "$install_tmp/previous" "$install_target"
    fi
  fi
}
trap rollback_install EXIT
git clone --quiet --depth 1 --branch v0.3.0 \
  https://github.com/trycopilotai/replx "$install_tmp/replx"
mkdir -p "$install_tmp/package"
cp -R "$install_tmp/replx/skill/." "$install_tmp/package/"
if [ -e "$install_target" ]; then
  mv "$install_target" "$install_tmp/previous"
fi
mv "$install_tmp/package" "$install_target"
trap - EXIT
rm -rf "$install_tmp"
```

Or from the marketplace, alongside the other
[trycopilot.ai skills](https://github.com/trycopilotai/skills):

```text
/plugin marketplace add trycopilotai/skills
/plugin install replx@trycopilotai
```

Invoke the directly installed skill as `/replx`, or the
marketplace plugin as `/replx:replx`, with either a command
or an end state:

```text
/replx make build
/replx the service is reachable and returns HTML
```

### Codex

Install the same tagged skill package:

```sh
set -eu
install_parent="$HOME/.agents/skills"
install_target="$install_parent/replx"
mkdir -p "$install_parent"
install_tmp="$(mktemp -d "$install_parent/.replx.XXXXXX")"
rollback_install() {
  if [ ! -e "$install_target" ]; then
    if [ -e "$install_tmp/previous" ]; then
      mv "$install_tmp/previous" "$install_target"
    fi
  fi
}
trap rollback_install EXIT
git clone --quiet --depth 1 --branch v0.3.0 \
  https://github.com/trycopilotai/replx "$install_tmp/replx"
mkdir -p "$install_tmp/package"
cp -R "$install_tmp/replx/skill/." "$install_tmp/package/"
if [ -e "$install_target" ]; then
  mv "$install_target" "$install_tmp/previous"
fi
mv "$install_tmp/package" "$install_target"
trap - EXIT
rm -rf "$install_tmp"
```

Or install it from the trycopilot.ai marketplace:

```sh
npx -y @openai/codex plugin marketplace add \
  trycopilotai/skills --ref main
npx -y @openai/codex plugin add \
  replx@trycopilotai
```

Invoke either Codex installation with a command or an end
state:

```text
$replx make build
$replx the service is reachable and returns HTML
```

The `v0.3.0` tagged repository carries Claude Code and
Codex plugin manifests. Both runtimes load the canonical
skill package under `skills/replx`; `skill/SKILL.md`
resolves to that package, so the skill content is stored
once.

The clone is pinned to a tag rather than to `main`. This
file is an instruction set that steers an agent, so a
mutable branch would silently change what your loop is told
to do. Read `SKILL.md` before you invoke it.

If the skills directory did not exist before you ran the
install, restart the session so it gets picked up.

## What it does differently

| A loop around an agent CLI                     | `replx`                                                                                                                                  |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Success is the exit status                     | Success is a condition you declare, and it can be stated in prose rather than measured by the command             |
| Retries the same state                         | One run per iteration, never wrapped in `until` or `while`                                                                               |
| A passing command ends the run                 | The protocol names the repairs that buy a pass and instructs against them; the harness scores the ones its checks catch as `bad_success` |
| Needs a runner installed                       | One complete skill package, read by the agent you already have                                                                           |
| Lint, build, and test cost the same every pass | Lint drops out once clean, and lint-only edits checkpoint separately                                                                     |
| Reports green                                  | Reports the condition met, or an honest unsolved with what was ruled out                                                                 |

## The repairs that do not count

Named in the protocol, because a loop that has not named
them will find them:

- Deleting or skipping the failing test.
- Loosening an assertion until it accepts the wrong value.
- Marking the failing path as expected to fail.
- Hardcoding a fixture so the assertion passes while the
  defect remains.
- Catching and discarding the error the test exists to
  detect.

An honest `unsolved` is worth more than a green command with
a weakened test, because the second one also removed the
signal that would have caught the defect later.

## Measuring that, instead of asserting it

[`eval/`](eval/README.md) is a harness that scores a model's
repair against an oracle the model cannot see. Held-out
checks live in a patch applied only at verification time, so
they cannot be read or edited. When a patch makes the
command pass but those checks or the guard catch it, the run
is recorded as `bad_success`, a distinct result from
`unsolved`. That detection is only as good as the case: a
shortcut no check happens to cover still scores as a solve,
which is why the most useful contribution is one that slips
through.

Three models have been scored so far, in
[`eval/RESULTS.md`](eval/RESULTS.md). `gpt-4.1` solves the
one case in a single iteration with the held-out checks
passing; two weaker models never produced an applicable
patch, which the results separate from a repair failure
rather than conflating. **No `bad_success` has been seen
from a real model yet**, so the headline claim is
demonstrated by the 25 offline tests and not yet
field-tested.

```sh
python3 -m unittest discover -s eval -q
```

Porting that harness out of a private repository turned up
three ways it had been leaking its own answer, all now
closed and each covered by a test. The most interesting one
was structural: the sandbox used to be a git worktree, and a
worktree carries the parent commit, which is the state
before the defect was seeded. `git diff`, `git log -p`, and
`git show` each handed over the original correct code.

## Prior art

Running a coding agent in a loop until a condition is met is
publicly known as the **Ralph Wiggum** technique. It was
named and described by
[Geoffrey Huntley](https://ghuntley.com/ralph/) in May 2025,
who put it as plainly as it deserves: "Ralph is a bash
loop."

The space is well populated. Star counts as of 2026-07-29:

- [`mikeyobrien/ralph-orchestrator`](https://github.com/mikeyobrien/ralph-orchestrator),
  3,076 stars, actively maintained, and the only one of
  these with a benchmark directory.
- [`michaelshimeles/ralphy`](https://github.com/michaelshimeles/ralphy),
  2,955 stars.
- [`fstandhartinger/ralph-wiggum`](https://github.com/fstandhartinger/ralph-wiggum),
  280 stars, and
  [`soderlind/ralph`](https://github.com/soderlind/ralph), 89.
- Claude Code ships a built-in `/loop`.

**The loop is table stakes and this repository does not
claim otherwise.** Every project above is a runner: a script
that invokes an agent from the outside. `replx` is a
protocol the agent runs itself, which is a difference but a
small one.

The difference worth having is the oracle.
`ralph-orchestrator`'s `bench/tasks.json` is two starter
tasks whose entire verification is one shell command.
Nothing in it distinguishes a fixed defect from a deleted
test. That gap is what `eval/` addresses, and it is the only
claim here that the incumbents do not already satisfy.

## What success looks like for this repo

Not stars. The metric that means this is working is
**contributed cases**, because each one makes the benchmark
harder to satisfy dishonestly. A case that catches a repair
the current checks accept is the most valuable thing anyone
can send.

## Layout

```text
replx/
  skill -> skills/replx compatibility path
  skills/replx/         the complete skill package
    SKILL.md            the protocol
    agents/openai.yaml  Codex interface metadata
  examples/             the fixture and a real run with its manifest
  eval/                 the harness, its cases, and its results
  assets/               logo and demo, regenerate with build.py
```

The demo and the social preview are generated, not hand
made. `python3 assets/build.py` rebuilds them, which needs
headless Chrome and ImageMagick. It looks for Chrome at the
macOS install path; set `CHROME` to override it elsewhere.
`python3 assets/check_rebuild.gpt.py` rebuilds all three
images in a copied checkout and fails unless every output is
byte-identical to the committed asset. Every text tone in
them is checked against 4.5:1 on the background. The GIF
loops, which exceeds the five-second threshold in WCAG
2.2.2, so the README wraps it in a `<picture>` whose
`prefers-reduced-motion` source is a static poster.

## Contributing

Issues and pull requests are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md). The most useful
contribution is a bad success the harness scored as solved.

`examples/smoke-oracle/` is deliberately broken. Do not run
it expecting a working router, and do not copy it. See
[SECURITY.md](SECURITY.md), which matters more here than for
most prompt repositories, because the harness applies
model-authored patches and runs commands out of a case file.

## FAQ

**How is this different from Claude Code's `/loop`?**

`/loop` re-runs a task on a schedule or until you stop it.
`replx` is aimed at one failing command, takes a bounded
budget, and instructs against calling a weakened test a
solve. They compose: `/loop` decides when to run, `replx`
decides what counts as done.

**Which agents does it work with?**

It is designed to be agent-agnostic: a prompt, not a
program. Claude Code 2.1.220 and Codex CLI 0.146.0 have
actually picked it up from their direct skill directories
and run it through `/replx` and `$replx`. The retained
[Claude Code final output](examples/claude-code-smoke-run.gpt.md)
and [Codex final run record](examples/codex-smoke-run.gpt.md)
have pinned manifests beside them. Results from other agents
are wanted, including negative ones.

**Does the benchmark leak the answer?**

Not any more, and there is a test that fails if it starts
to. `test_repair_prompt_never_reveals_the_oracle` checks
every line unique to the held-out patch against every prompt
in the run, plus the case description. The semantic guard is
deliberately not hidden: it pins text from the visible test,
so the model was shown it anyway. The version this was
ported from wrote the expected value into the prompt
outright.

**Why one run per iteration instead of a retry loop?**

Because a retry re-runs the same state and a loop re-runs
the same reasoning. Forcing one attempt per iteration makes
each one a fresh diagnosis against the current failure,
which is also what makes the phase-aware step below
possible.

**What is the phase-aware behaviour for?**

Cost. On a combined lint, build, and test driver, lint
usually goes green first and then keeps charging for every
subsequent iteration. The protocol drops it once clean,
checkpoints any lint-only edits separately so formatting
stays out of the fix, and runs lint once more at the end
before declaring success.

**Why is it called `replx` when it is not a REPL?**

The `x` is execution: it runs your command, reads the
failure, and edits. The name predates this repository. Note
that the PyPI package `replx` is an unrelated MicroPython
tool, and `replxx` is an unrelated readline library.

**Is a bounded budget not just giving up early?**

Giving up is the point of the bound. An unbounded loop with
no oracle converges on whatever makes the command stop
complaining. A budget forces the run to report what it ruled
out, which is information you can act on.

## License

MIT. See [LICENSE](LICENSE).

## Not affiliated with GitHub

`trycopilot.ai` is an independent project. It is not
affiliated with, endorsed by, or connected to GitHub,
Microsoft, or GitHub Copilot. The name is a domain the
author owns and predates this repository.
