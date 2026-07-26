<p align="center">
  <img src="assets/logo.svg" alt="" width="84" height="84">
</p>

<h1 align="center">replx</h1>

<p align="center"><strong>A repair loop that does not accept exit 0 as proof.</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license">
  <img src="https://img.shields.io/badge/dependencies-none-brightgreen.svg" alt="No dependencies">
  <img src="https://img.shields.io/badge/install-one%20markdown%20file-blue.svg" alt="One markdown file">
  <img src="https://img.shields.io/badge/oracle-not%20the%20exit%20status-8957e5.svg" alt="The oracle is not the exit status">
</p>

`replx` drives a failing command to green in bounded
iterations, one attempt per iteration, each with a fresh
diagnosis. That part is not new.

What it adds is a success condition you have to state. Many
checks exit 0 while printing a failure, and the cheapest way
to make any command pass is to stop it from checking.
`replx` declares the condition before the first iteration
and names the repairs that are not allowed to count.

It is one Markdown file with no dependencies and no runtime.
There is nothing to install beyond the agent you already
use.

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
with every request misrouted. That is not a contrived
script. Health checks, smoke suites, and deploy verifiers
behave this way constantly, because they are written to
report rather than to gate.

The other half of the problem runs the opposite way. When a
command does fail honestly, the fastest repair is often to
delete the assertion. Both failures look like success.

## A real run

![replx repairing a router whose smoke check exits 0 while reporting two failures, then verifying the fix](assets/demo.gif)

One iteration. The agent also declined the cheaper repair
and said why: reordering the route table turns the check
green, but it leaves first-match semantics under a comment
promising longest-prefix, so any later append can silently
shadow an existing route. It changed the lookup instead.

Transcript, input, and run manifest:
[`examples/smoke-oracle-run.md`](examples/smoke-oracle-run.md).

## Use it

Paste [`skill/SKILL.md`](skill/SKILL.md) into your agent as
the instructions, then give it a failing command. That is
the whole contract.

As a Claude Code skill:

```sh
D=$(mktemp -d) \
  && git clone --quiet --depth 1 --branch v0.1.0 \
       https://github.com/trycopilotai/replx "$D/replx" \
  && mkdir -p ~/.claude/skills/replx \
  && cp "$D/replx/skill/SKILL.md" ~/.claude/skills/replx/ \
  && rm -rf "$D"
```

Or from the marketplace, alongside the other
[trycopilot.ai skills](https://github.com/trycopilotai/skills):

```text
/plugin marketplace add trycopilotai/skills
/plugin install replx@trycopilot
```

The clone is pinned to a tag rather than to `main`. This
file is an instruction set that steers an agent, so a
mutable branch would silently change what your loop is told
to do. Read `SKILL.md` before you invoke it.

Then invoke it by name, with either a command or an end
state:

```text
/replx make build
/replx the service is reachable and returns HTML
```

If the skills directory did not exist before you ran the
install, restart the session so it gets picked up.

## What it does differently

| A loop around an agent CLI                     | `replx`                                                                  |
| ---------------------------------------------- | ------------------------------------------------------------------------ |
| Success is the exit status                     | Success is a condition you declare, and it can be a line of output       |
| Retries the same state                         | One run per iteration, never wrapped in `until` or `while`               |
| A passing command ends the run                 | A passing command that weakened a test is a failure with its own name    |
| Needs a runner installed                       | One Markdown file, read by the agent you already have                    |
| Lint, build, and test cost the same every pass | Lint drops out once clean, and lint-only edits checkpoint separately     |
| Reports green                                  | Reports the condition met, or an honest unsolved with what was ruled out |

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
they cannot be read or edited. A patch that makes the
command pass without fixing the defect is recorded as
`bad_success`, which is a distinct result from `unsolved`.

**No model has been scored yet**, because no endpoint was
reachable when this was built.
[`eval/RESULTS.md`](eval/RESULTS.md) says so at the top
rather than in a footnote. What is verified is the
instrument: 13 offline tests, no network and no model
required.

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

The space is well populated. Star counts as of 2026-07-26:

- [`mikeyobrien/ralph-orchestrator`](https://github.com/mikeyobrien/ralph-orchestrator),
  3,075 stars, actively maintained, and the only one of
  these with a benchmark directory.
- [`michaelshimeles/ralphy`](https://github.com/michaelshimeles/ralphy),
  2,948 stars.
- [`fstandhartinger/ralph-wiggum`](https://github.com/fstandhartinger/ralph-wiggum),
  277 stars, and
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
  skill/SKILL.md        the protocol
  examples/             the fixture and a real run with its manifest
  eval/                 the harness, its cases, and its results
  assets/               logo and demo
```

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
budget, and will not call it solved on a passing command
that weakened a test. They compose: `/loop` decides when to
run, `replx` decides what counts as done.

**Which agents does it work with?**

Any agent that follows written instructions. It is a prompt,
not a program. **Only Claude Code 2.1.220 has actually been
run against it**, and the transcript is in `examples/`.
Results from other agents are wanted, including negative
ones.

**Does the benchmark leak the answer?**

Not any more, and there is a test that fails if it starts
to. `test_repair_prompt_never_reveals_the_oracle` checks
every line the held-out patch adds against every prompt in
the run, plus the guard substrings and the case description.
The version this was ported from wrote the expected value
into the prompt outright.

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
