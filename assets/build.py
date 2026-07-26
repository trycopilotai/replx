#!/usr/bin/env python3
"""Regenerate assets/: the social preview and the demo GIF.

Renders HTML through headless Chrome, because ImageMagick's
internal SVG renderer drops arc paths and strokes.

Every text tone used here was checked against #0d1117 for WCAG
1.4.3 and clears 4.5:1. #6e7681 is deliberately absent; it
measures 4.12:1 and is the tone the l8 demo had to replace.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
OUT = ASSETS / ".frames"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

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

SHELL = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ background:{bg}; }}
  body {{
    width:{w}px; height:{h}px;
    font-family:{font};
    font-size:17px; line-height:1.55;
    color:{fg};
    padding:26px 30px;
    -webkit-font-smoothing:antialiased;
  }}
  .dim {{ color:{dim}; }}
  .green {{ color:{green}; }}
  .red {{ color:{red}; }}
  .amber {{ color:{amber}; }}
  .blue {{ color:{blue}; }}
  .b {{ font-weight:700; }}
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

PROMPT = '<span class="green b">$</span> '

FRAMES = [
    # 1. the problem
    PROMPT + './smoke.sh\n'
    '<span class="dim">  /api/v1/orders  -> notfound, wanted api</span>\n'
    '<span class="dim">  /static/app.css -> notfound, wanted static</span>\n'
    '<span class="red b">smoke: FAIL 2 of 3 checks</span>\n'
    + PROMPT + 'echo $?\n'
    '<span class="amber b">0</span>\n'
    '\n'
    '<span class="dim">Two routes broken. The shell was told</span>\n'
    '<span class="amber">everything is fine.</span>',

    # 2. invocation
    PROMPT + './smoke.sh\n'
    '<span class="dim">  /api/v1/orders  -> notfound, wanted api</span>\n'
    '<span class="dim">  /static/app.css -> notfound, wanted static</span>\n'
    '<span class="red b">smoke: FAIL 2 of 3 checks</span>\n'
    + PROMPT + 'echo $?\n'
    '<span class="amber b">0</span>\n'
    '\n'
    + PROMPT + '<span class="blue b">/replx the smoke check passes</span>',

    # 3. condition declared, one iteration
    '<span class="blue b">replx: the smoke check passes</span>\n'
    '\n'
    '<span class="dim">Success condition:</span> a line beginning '
    '<span class="green">smoke: PASS</span>\n'
    '<span class="dim">Budget:</span> 4 iterations\n'
    '\n'
    '<span class="b">Iteration 1</span>\n'
    '  <span class="dim">Command:</span> ./smoke.sh\n'
    '  <span class="dim">Result:</span> exit <span class="amber">0</span>, '
    'and <span class="red">smoke: FAIL 2 of 3</span>\n'
    '           <span class="amber b">-> not success</span>\n'
    '  <span class="dim">Diagnosis:</span> first-match table, '
    '"/" shadows every prefix\n'
    '  <span class="dim">Fix:</span> route() selects the '
    '<span class="b">longest</span> matching prefix',

    # 4. verified, and the declined shortcut
    '<span class="b">Iteration 1</span>\n'
    '  <span class="dim">Fix:</span> route() selects the '
    '<span class="b">longest</span> matching prefix\n'
    '  <span class="dim">Verify:</span> ./smoke.sh -> '
    '<span class="green b">smoke: PASS 3 checks</span>\n'
    '\n'
    '<span class="b">Outcome</span>\n'
    '  <span class="dim">Status:</span> '
    '<span class="green b">solved</span>\n'
    '  <span class="dim">Iterations used:</span> 1/4\n'
    '  <span class="dim">Declined:</span> reordering ROUTES. It also\n'
    '  turns the check green and leaves the trap in place.\n'
    '\n'
    '<span class="dim">Exit status was</span> '
    '<span class="amber">0</span> '
    '<span class="dim">before and after. It never</span>\n'
    '<span class="dim">carried any information.</span>',
]

PREVIEW = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ background:{bg}; width:1280px; height:640px; }}
  body {{
    font-family:{font};
    color:{fg};
    display:flex; flex-direction:column;
    align-items:center; justify-content:center;
    text-align:center;
  }}
  .mark {{ width:132px; height:132px; margin-bottom:34px; }}
  h1 {{ font-size:104px; letter-spacing:-2px; font-weight:700; }}
  .tag {{
    font-size:33px; color:{fg}; margin-top:18px;
    font-weight:600;
  }}
  .sub {{ font-size:25px; color:{dim}; margin-top:30px; }}
  .zero {{ color:{amber}; }}
</style></head><body>
  <svg class="mark" viewBox="0 0 512 512" role="img"
       aria-label="replx">
    <rect width="512" height="512" rx="112" fill="#161b22"/>
    <rect x="4" y="4" width="504" height="504" rx="108"
          fill="none" stroke="#30363d" stroke-width="8"/>
    <path d="M 256 106 A 150 150 0 1 1 106 256" fill="none"
          stroke="#3fb950" stroke-width="40"/>
    <path d="M 106 186 L 148 262 L 64 262 Z" fill="#3fb950"/>
    <circle cx="150" cy="150" r="30" fill="#d29922"/>
  </svg>
  <h1>replx</h1>
  <div class="tag">A repair loop that does not assume
    <span class="zero">exit 0</span> means success.</div>
  <div class="sub">github.com/trycopilotai/replx</div>
</body></html>
"""


def shoot(html: str, width: int, height: int, out: Path) -> None:
    src = out.with_suffix(".html")
    src.write_text(html, encoding="utf-8")
    subprocess.run(
        [
            CHROME,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            "--screenshot=" + str(out),
            "--window-size=%d,%d" % (width, height),
            "file://" + str(src),
        ],
        check=True,
        capture_output=True,
    )
    src.unlink()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    width, height = 1000, 400

    for index, body in enumerate(FRAMES, start=1):
        html = SHELL.format(
            bg=BG, fg=FG, dim=DIM, green=GREEN, red=RED,
            amber=AMBER, blue=BLUE, font=FONT,
            w=width, h=height, body=body,
        )
        target = OUT / ("frame-%02d.png" % index)
        shoot(html, width, height, target)
        print("  wrote " + target.name)

    shoot(
        PREVIEW.format(bg=BG, fg=FG, dim=DIM, amber=AMBER, font=FONT),
        1280,
        640,
        ASSETS / "social-preview.png",
    )
    print("  wrote social-preview.png")

    # Per-frame delays in centiseconds; one cycle is 4.6s.
    #
    # The demo loops. An earlier version played once, which is
    # clean against WCAG 2.2.2 and useless in practice: a README
    # GIF starts on page load and is finished before a reader has
    # scrolled to it, so it reads as a static screenshot.
    #
    # Looping motion exceeds the 5s threshold in 2.2.2, so this
    # is a deliberate trade rather than a conformance claim. The
    # mitigation is the poster: README.md wraps the GIF in a
    # <picture> whose prefers-reduced-motion source serves
    # demo-poster.png, so a reader who has asked their OS for
    # less motion gets the still frame instead.
    delays = ["100", "80", "120", "160"]
    args = ["magick"]
    for delay, index in zip(delays, range(1, len(FRAMES) + 1)):
        args += ["-delay", delay, str(OUT / ("frame-%02d.png" % index))]
    args += [
        "-resize", "1000x400", "-colors", "128", "-layers", "Optimize",
        str(OUT / "raw.gif"),
    ]
    subprocess.run(args, check=True, capture_output=True)
    subprocess.run(
        ["magick", str(OUT / "raw.gif"), "-loop", "0",
         str(ASSETS / "demo.gif")],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["magick", str(OUT / "frame-04.png"), "-resize", "1000x400",
         str(ASSETS / "demo-poster.png")],
        check=True, capture_output=True,
    )
    print("  wrote demo.gif and demo-poster.png")
    shutil.rmtree(OUT, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
