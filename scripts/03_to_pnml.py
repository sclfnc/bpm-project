#!/usr/bin/env python3
"""Convert every .bpmn under bpmn/ to PNML, into pnml/.

    python3 scripts/03_to_pnml.py

Which files exist is the whole configuration. bpmn2petrinet is a browser
application, so it runs headless against a local server: ES modules and fetch
are both blocked over file://. Needs Chromium at the hardwired path below; not
portable, and not trying.

The converter's code is used unmodified, with one setting of its own turned on,
withCollapsedXor. Two conformance defects in its output are repaired afterwards,
each documented beside its repair.
"""
import html
import json
import re
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BPMN = ROOT / 'bpmn'
OUT = ROOT / 'pnml'

BROWSER = '/usr/bin/chromium'    # any Chromium-family build takes these flags
LOAD_BUDGET_MS = 25_000          # virtual time, so it is not wall-clock patience


class QuietHandler(SimpleHTTPRequestHandler):
    """The stock file server with its logging removed: one line per module
    fetched, times six diagrams, buries the only output worth reading."""

    def log_message(self, *args):
        pass


# --------------------------------------------------------------------------
# The two repairs
# --------------------------------------------------------------------------

# In PNML a node's graphics carry a <position> and an annotation's an <offset>.
# The converter writes <position> in both cases, once per node in every net.
# WoPeD reads the file anyway; ProM validates against the schema and returns
# zero results with no explanation, so this rename is what makes these files
# importable at all.
#
# Textual rather than a parse-and-serialise round trip, on purpose: re-writing
# would reformat every line of a file delivered as evidence, and bury the one
# difference that matters in the diff against the converter's own output.
ANNOTATION = re.compile(r'<name>.*?</name>', re.S)


def fix_annotation_graphics(pnml):
    """<position> is for nodes, <offset> for annotations, and <name> is the
    only annotation the converter emits."""
    return ANNOTATION.sub(
        lambda m: m.group(0).replace('<position ', '<offset '), pnml)


def name_net(pnml, name):
    """Give the net an id and a type, which the standard asks for and the
    converter omits."""
    tagged, count = re.subn(r'<net>', f'<net id="{name}" type="PTNet">',
                            pnml, count=1)
    # A silent no-op here would ship an unnamed net that still looks fine.
    if count != 1:
        sys.exit(f'{name}: no bare <net> element to name; the converter output '
                 'has changed shape')
    return tagged


# --------------------------------------------------------------------------
# Driving the converter
# --------------------------------------------------------------------------

# The page the headless browser opens, written here rather than kept in
# bpmn2petrinet/, which is an upstream checkout and not part of this
# repository: a driver left inside it would be lost on the next pull, and the
# setting below would travel with the checkout instead of with the project.
#
# withCollapsedXor keeps an exclusive gateway as one place with its branch
# transitions competing on it. With the flag off the converter adds a
# "<branch> Choosing" transition and a "<branch> Chosen" place per branch,
# nodes that correspond to nothing in the diagram. Every verdict is the same
# either way, and the labels read as the diagram's own.
DRIVER = """<!doctype html><html><body><pre id="out">running</pre>
<script type="module">
import {Importer, Parser, Converter, Exporter} from "./src/bpmn2petri/index.js";
import Config from "./src/bpmn2petri/config.js";
Config.withCollapsedXor = true;
const out = document.getElementById("out");
try {
  const xml = await (await fetch(new URLSearchParams(location.search).get("f"))).text();
  const imp = new Importer(); await imp.importString(xml);
  const bpmn = new Parser(imp.XML).BPMN;
  const net = new Converter(bpmn).convert();
  const exp = new Exporter(net); exp.exportAll();
  out.textContent = JSON.stringify({
    counts: {places: net.places.size, transitions: net.transitions.size, arcs: net.arcs.size},
    system: exp.getResult(),
    pools: exp.getPools()
  });
} catch (e) { out.textContent = "ERROR: " + (e && e.stack || e); }
</script></body></html>
"""
DRIVER_NAME = '_convert_driver.html'

RESULT = re.compile(r'<pre id="out">(.*?)</pre>', re.S)


def convert(port, src):
    """Drive the converter over one diagram and return its PNML and counts."""
    relative = src.resolve().relative_to(ROOT).as_posix()
    dom = subprocess.run(
        [BROWSER, '--headless', '--disable-gpu', '--no-sandbox',
         f'--virtual-time-budget={LOAD_BUDGET_MS}', '--dump-dom',
         f'http://127.0.0.1:{port}/bpmn2petrinet/{DRIVER_NAME}?f=/{relative}'],
        check=True, capture_output=True, text=True).stdout

    found = RESULT.search(dom)
    if not found:
        sys.exit(f'{src.name}: the converter page produced no result element. '
                 f'First 500 characters of the DOM:\n{dom[:500]}')
    body = found.group(1)
    if body.startswith('ERROR'):
        sys.exit(f'{src.name}: {body[:1500]}')

    # --dump-dom serialises the page, so the JSON in the <pre> comes back
    # HTML-escaped. html.unescape reverses it in one pass, which matters:
    # undoing the entities one replacement at a time expands &amp;quot; twice
    # and turns it into a bare quote.
    result = json.loads(html.unescape(body))
    pnml = name_net(fix_annotation_graphics(result['system']), src.stem)
    return pnml, result['counts']


# --------------------------------------------------------------------------

def main():
    if not Path(BROWSER).exists():
        sys.exit(f'{BROWSER} not found; edit BROWSER at the top of this script')
    sources = sorted(BPMN.glob('*.bpmn'))
    if not sources:
        sys.exit(f'no .bpmn under {BPMN}')

    # Port 0 lets the kernel pick a free port and the server keeps it. Picking
    # one first with a throwaway socket leaves a window for someone else.
    server = ThreadingHTTPServer(('127.0.0.1', 0),
                                 partial(QuietHandler, directory=str(ROOT)))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    (ROOT / 'bpmn2petrinet' / DRIVER_NAME).write_text(DRIVER)

    OUT.mkdir(parents=True, exist_ok=True)
    try:
        for src in sources:
            pnml, counts = convert(port, src)
            (OUT / f'{src.stem}.pnml').write_text(pnml)
            print(f"{src.stem}.pnml: {counts['places']}P"
                  f" / {counts['transitions']}T / {counts['arcs']}A")
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
