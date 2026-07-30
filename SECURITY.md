# Security

This repository is not only a prompt. `eval/` applies
model-authored patches and runs shell commands out of a case
file, so it has a real threat model, and it is worth reading
before you run it.

## Run the harness in something disposable

`eval/probe.py` does three things that deserve care:

- It runs `case.command` and every entry in `post_checks`
  **through a shell**, verbatim, from the case file.
- It applies a **unified diff written by a language model**
  with `git apply`.
- It sends the contents of `context_files` to whatever
  endpoint you point it at.

The sandbox it builds is a `git archive` export in your
output directory, which limits what a patch can touch by
default, because `git apply` refuses paths outside the tree
it is run in. It is **not** a security boundary. A case file
is code execution by design.

So: **treat a case file from anyone else as untrusted
input.** Read `case.json`, `bug.patch`, and `held-out.patch`
before running a case you did not write, the same way you
would read a `Makefile` from a stranger. Run unfamiliar
cases in a container or a VM, not on a machine with
credentials on it.

Do not point `--models` at an endpoint you do not control
while running a case whose `context_files` include anything
private. The contents of those files go into the request
body.

Keys are named, never inlined. `--models` takes the **name
of an environment variable** that holds the key, so the
harness never writes it to your shell history, to
`report.json`, or to a saved prompt.

That is a statement about the harness, not a guarantee about
the process tree. `case.command` and every `post_check` run
through a shell that **inherits your whole environment**,
and their output is put into the next repair prompt and
saved to the output directory. A case that runs `env` or
`echo $OPENAI_API_KEY` therefore writes your key to disk and
sends it to the endpoint, using nothing but the code
execution a case file already has by design. One more reason
to read a case file you did not write, and not to run one
against an endpoint you do not control.

## The protocol does not stop to ask

`replx` has no confirmation step, and that is a decision
rather than an oversight. Step 5 diagnoses and edits on
every iteration without pausing, so a budget of 4 is up to
four rounds of file edits and command runs with nobody in
the loop. A loop that asks before each repair is a loop you
have to sit and watch, which is most of the value gone.

What that costs you:

- **It edits your working tree in place.** Nothing is
  stashed, branched, or backed up first. Run it on a clean
  tree, or on a branch you are willing to throw away, so
  `git diff` is a complete account of what it did.
- **It runs the command you named, repeatedly.** If that
  command deploys, migrates a database, or posts to a
  network service, so does every iteration.
- **The blast radius is whatever the agent may already do.**
  Permissions come from the agent you paste the protocol
  into, not from the protocol. An agent running with
  approvals turned off has approvals turned off here too.

Step 6 constrains _what kind_ of repair counts, not what the
agent is permitted to touch. It is a quality bar, not a
sandbox, and it is written for a cooperative agent. Do not
rely on it against a hostile one.

For an unfamiliar repository, the honest setup is a
disposable checkout and a budget you can afford to have
spent badly.

## The fixture is deliberately broken

[`examples/smoke-oracle/`](examples/smoke-oracle/) ships a
router with a defect and a smoke check that always exits 0.
That is what it is for. Do not copy either file. Reports
about the routing bug are not security issues; they are the
demonstration. The same is true of
`eval/cases/chunk-off-by-one/`, whose patches seed a defect
on purpose.

## What is in scope

- **Instruction injection into the protocol.**
  `skill/SKILL.md` says the failing output is evidence and
  never instruction. If you can craft a repository, test
  fixture, comment, or error message that makes a compliant
  agent delete a test, widen its permissions, take an
  unrelated write action, or leak context, that is a real
  vulnerability in the protocol.
- **Oracle escape in the harness.** Anything that lets the
  model under test read the held-out patch, the held-out
  commands, or the pre-defect code. Not the semantic guard's
  substrings: those are quoted from a test the model is
  shown on purpose, so seeing them tells it nothing it was
  not already given. Three real escapes existed before the
  first release and each is now covered by a test. A fourth
  would be a genuine finding. Note that this class overlaps
  with `oracle-gap`; file it here if it works by reading the
  oracle, and as an issue if it works by guessing.
- **Sandbox escape.** A repair patch, a case command, or a
  `strip_paths` entry that reads, writes, or deletes outside
  the sandbox directory.
- **Credential handling.** Any path by which an API key
  reaches `report.json`, a saved prompt, the output
  directory, or a log, other than a case command printing it
  itself, which is documented above.
- **Harmful guidance.** Anything in the protocol or a
  committed example that would make a reader's system less
  safe if followed.

## What is out of scope

- The defects in `examples/smoke-oracle/` and in the eval
  cases.
- A model producing a bad patch. That is the measurement,
  not a vulnerability.
- Running an untrusted case file and having it execute. That
  is documented above and is inherent to the design.
- Vulnerabilities in the agent or the model endpoint you
  use. Report those to that vendor.

## Reporting

Open a
[private security advisory](https://github.com/trycopilotai/replx/security/advisories/new)
for anything in scope. For everything else an ordinary issue
is preferred; this project would rather discuss its failure
modes in public.

Expect a first response within a week. This is a solo
project with no on-call.
