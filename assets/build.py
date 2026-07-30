#!/usr/bin/env python3
"""Regenerate assets/: the social preview and the demo GIF.

The demo is **derived from the committed transcript**, not
authored here. `examples/smoke-oracle-run.md` is parsed for its
iteration and outcome sections, and the frames are built from
what it says. Nothing about the run is typed into this file.

That is deliberate. An earlier version hand-wrote the frame
text and it drifted: the animation claimed `Iterations used:
1/4` from the first recorded run while the transcript and the
README both said 2/4. A reader watching the demo was being told
a number the repository contradicted two screens below. Parsing
the transcript makes that class of drift impossible, and
`test_demo_matches_the_transcript` fails if this file starts
inventing content again.

The animation **accumulates**. Each frame is the previous frame
plus new lines; nothing that appears ever leaves. The earlier
version was four slides that replaced one another, so content
at a given position vanished and was overwritten, which reads
as the earlier output scrolling up and out of view. The canvas
height is computed from the finished session rather than
guessed, so no line is ever clipped and nothing scrolls.

Rendered through headless Chrome, because ImageMagick's
internal SVG renderer drops arc paths and strokes.

Every text tone was checked against #0d1117 for WCAG 1.4.3 and
clears 4.5:1. #6e7681 is deliberately absent; it measures
4.12:1.

Needs headless Chrome and ImageMagick.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
REPO = ASSETS.parent
OUT = ASSETS / ".frames"
TRANSCRIPT = REPO / "examples" / "smoke-oracle-run.md"
# Overridable, because the default is a macOS install path and
# the README documents this command as one anyone can run.
CHROME = os.environ.get(
    "CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

BG = "#0d1117"
FG = "#e6edf3"
DIM = "#8b949e"      # 6.15:1
GREEN = "#56d364"    # 9.82:1
RED = "#f85149"      # 5.65:1
AMBER = "#e3b341"    # 9.72:1
BLUE = "#58a6ff"     # 7.49:1

FONT = (
    "ui-monospace, SFMono-Regular, Menlo, Monaco, "
    "'Cascadia Mono', 'Roboto Mono', monospace"
)

WIDTH = 1000
LINE_PX = 27          # 17px at 1.55 line-height, rounded up
CHROME_PX = 58        # top padding plus the three window dots
BOTTOM_PAD = 26


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def strip_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    return re.sub(r"`(.+?)`", r"\1", text)


def clip(text: str, limit: int) -> str:
    text = strip_md(text)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def read_headline() -> str:
    """The README's headline, so the preview cannot contradict it.

    This used to be typed into PREVIEW directly, and it went
    stale the moment the README was reworded: the social card
    still promised a loop that distrusts exit codes after the
    page above it had stopped claiming that.
    """
    text = (REPO / "README.md").read_text(encoding="utf-8")
    found = re.search(
        r'<p align="center"><strong>(.+?)</strong></p>', text)
    if not found:
        raise SystemExit("README has no centred headline to read")
    return found.group(1).strip()


def read_transcript() -> dict:
    """Pull the run's facts out of the committed transcript."""
    text = TRANSCRIPT.read_text(encoding="utf-8")

    def field(section: str, label: str) -> str:
        block = re.search(
            r"^## " + re.escape(section) + r"\n(.*?)(?=\n## |\n---|\Z)",
            text, re.S | re.M)
        if not block:
            raise SystemExit("transcript has no '## %s' section" % section)
        found = re.search(
            r"^- \*{0,2}" + re.escape(label) + r"\*{0,2}:\*{0,2}\s*(.+?)(?=\n- |\Z)",
            block.group(1), re.S | re.M)
        if not found:
            raise SystemExit("'%s' has no '%s' field" % (section, label))
        return " ".join(found.group(1).split())

    header = re.search(r"^# replx: (.+)$", text, re.M)
    if not header:
        raise SystemExit("transcript has no '# replx: ...' heading")
    console = re.search(r"```console\n(\$ \./smoke\.sh\n.*?)```", text, re.S)
    if not console:
        raise SystemExit("transcript has no failing-run console block")
    budget = re.search(r"^- \*{0,2}Budget\*{0,2}:\*{0,2}\s*(.+)$", text, re.M)
    condition = re.search(
        r"^- \*{0,2}Success condition\*{0,2}:\*{0,2}\s*(.+?)(?=\n- )",
        text, re.S | re.M)

    condition_text = ""
    if condition:
        condition_text = " ".join(condition.group(1).split())

    budget_text = ""
    if budget:
        budget_text = budget.group(1).strip()

    return {
        "target": header.group(1).strip(),
        "before": console.group(1).rstrip("\n").splitlines(),
        "condition": condition_text,
        "budget": budget_text,
        "i1_result": field("Iteration 1", "Result"),
        "i1_fix": field("Iteration 1", "Fix"),
        "i2_result": field("Iteration 2", "Result"),
        "status": field("Outcome", "Status"),
        "iterations": field("Outcome", "Iterations used"),
    }


def build_steps(run: dict) -> list[list[str]]:
    """Cumulative steps: each is the previous plus new lines."""
    prompt = '<span class="green b">$</span> '
    lines: list[str] = []
    steps: list[list[str]] = []

    def add(*new: str) -> None:
        lines.extend(new)
        steps.append(list(lines))

    before = run["before"]
    failing = [l for l in before if l.startswith("smoke:")][0]
    detail = [l for l in before if l.startswith("  /")]

    # before[0] already carries its own "$ " from the console
    # block, so strip it rather than rendering two prompts.
    add(prompt + esc(before[0].lstrip("$ ")))
    add(*['<span class="dim">%s</span>' % esc(l) for l in detail])
    add('<span class="red b">%s</span>' % esc(failing),
        prompt + "echo $?",
        '<span class="amber b">0</span>')
    add("", '<span class="dim">The check failed. The shell was told'
            ' everything is fine.</span>')
    add("", prompt + '<span class="blue b">/replx %s</span>'
        % esc(run["target"]))
    add("",
        '<span class="dim">Success condition:</span> '
        '<span class="green">%s</span>' % esc(clip(run["condition"], 56)),
        '<span class="dim">Budget:</span> %s' % esc(run["budget"]))
    add("", '<span class="b">Iteration 1</span>',
        '  <span class="dim">Result:</span> %s'
        % esc(clip(run["i1_result"], 64)))
    add('  <span class="dim">Fix:</span> %s' % esc(clip(run["i1_fix"], 64)))
    add("", '<span class="b">Iteration 2</span>',
        '  <span class="dim">Result:</span> '
        '<span class="green">%s</span>' % esc(clip(run["i2_result"], 60)))
    add("", '<span class="b">Outcome</span>',
        '  <span class="dim">Status:</span> '
        '<span class="green b">%s</span>' % esc(strip_md(run["status"])),
        '  <span class="dim">Iterations used:</span> %s'
        % esc(strip_md(run["iterations"])))
    return steps


SHELL = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ background:{bg}; }}
  body {{
    width:{w}px; height:{h}px;
    font-family:{font}; font-size:17px; line-height:1.55;
    color:{fg}; padding:26px 30px;
    -webkit-font-smoothing:antialiased;
  }}
  .dim {{ color:{dim}; }} .green {{ color:{green}; }}
  .red {{ color:{red}; }} .amber {{ color:{amber}; }}
  .blue {{ color:{blue}; }} .b {{ font-weight:700; }}
  .chrome {{ display:flex; gap:8px; margin-bottom:20px; }}
  .dot {{ width:12px; height:12px; border-radius:50%; }}
  pre {{ white-space:pre-wrap; font-family:inherit; }}
</style></head><body>
<div class="chrome">
  <div class="dot" style="background:#f85149"></div>
  <div class="dot" style="background:#e3b341"></div>
  <div class="dot" style="background:#56d364"></div>
</div>
<pre>{body}</pre>
</body></html>
"""

PREVIEW = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ background:{bg}; width:1280px; height:640px; }}
  body {{ font-family:{font}; color:{fg}; display:flex;
    flex-direction:column; align-items:center;
    justify-content:center; text-align:center; }}
  .mark {{ width:132px; height:132px; margin-bottom:34px; }}
  h1 {{ font-size:104px; letter-spacing:-2px; font-weight:700; }}
  .tag {{ font-size:33px; margin-top:18px; font-weight:600; }}
  .sub {{ font-size:25px; color:{dim}; margin-top:30px; }}
  .zero {{ color:{amber}; }}
</style></head><body>
  <svg class="mark" viewBox="0 0 512 512" role="img" aria-label="replx">
    <rect width="512" height="512" rx="112" fill="#161b22"/>
    <rect x="4" y="4" width="504" height="504" rx="108"
          fill="none" stroke="#30363d" stroke-width="8"/>
    <path d="M 256 106 A 150 150 0 1 1 106 256" fill="none"
          stroke="#3fb950" stroke-width="40"/>
    <path d="M 106 186 L 148 262 L 64 262 Z" fill="#3fb950"/>
    <circle cx="150" cy="150" r="30" fill="#d29922"/>
  </svg>
  <h1>replx</h1>
  <div class="tag">{headline}</div>
  <div class="sub">github.com/trycopilotai/replx</div>
</body></html>
"""


def shoot(html: str, width: int, height: int, out: Path) -> None:
    if not Path(CHROME).exists():
        raise SystemExit(
            "no Chrome at %s. Set CHROME to your headless-capable "
            "Chrome or Chromium binary." % CHROME)
    src = out.with_suffix(".html")
    src.write_text(html, encoding="utf-8")
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=2", "--screenshot=" + str(out),
         "--window-size=%d,%d" % (width, height), "file://" + str(src)],
        check=True, capture_output=True)
    src.unlink()


def main() -> int:
    if not TRANSCRIPT.exists():
        raise SystemExit("missing transcript: " + str(TRANSCRIPT))
    OUT.mkdir(parents=True, exist_ok=True)

    run = read_transcript()
    steps = build_steps(run)
    height = CHROME_PX + LINE_PX * len(steps[-1]) + BOTTOM_PAD
    print("  %d frames, %d final lines, canvas %dx%d"
          % (len(steps), len(steps[-1]), WIDTH, height))

    for index, body in enumerate(steps, start=1):
        html = SHELL.format(bg=BG, fg=FG, dim=DIM, green=GREEN, red=RED,
                            amber=AMBER, blue=BLUE, font=FONT,
                            w=WIDTH, h=height, body="\n".join(body))
        shoot(html, WIDTH, height, OUT / ("frame-%02d.png" % index))

    shoot(PREVIEW.format(bg=BG, fg=FG, dim=DIM, amber=AMBER, font=FONT,
                         headline=esc(read_headline())),
          1280, 640, ASSETS / "social-preview.png")

    # Short even delays so it reads as output arriving rather
    # than slides changing, with a long hold on the outcome.
    args = ["magick"]
    for index in range(1, len(steps) + 1):
        delay = "48"
        if index == len(steps):
            delay = "150"
        args += ["-delay", delay,
                 str(OUT / ("frame-%02d.png" % index))]
    args += ["-resize", "%dx%d" % (WIDTH, height), "-colors", "64",
             "-layers", "Optimize", str(OUT / "raw.gif")]
    subprocess.run(args, check=True, capture_output=True)

    # Loops. A play-once GIF finishes before a reader scrolls to
    # it and reads as a screenshot. Looping motion exceeds the 5s
    # threshold in WCAG 2.2.2, so README.md wraps it in a
    # <picture> whose prefers-reduced-motion source is the poster.
    subprocess.run(["magick", str(OUT / "raw.gif"), "-loop", "0",
                    str(ASSETS / "demo.gif")], check=True,
                   capture_output=True)
    subprocess.run(["magick", str(OUT / ("frame-%02d.png" % len(steps))),
                    "-resize", "%dx%d" % (WIDTH, height),
                    "-strip",
                    str(ASSETS / "demo-poster.png")], check=True,
                   capture_output=True)
    print("  wrote demo.gif, demo-poster.png, social-preview.png")
    shutil.rmtree(OUT, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
