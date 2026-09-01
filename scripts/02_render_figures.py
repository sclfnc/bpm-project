#!/usr/bin/env python3
"""Render every .bpmn under bpmn/ as a vector PDF, into bpmn/img/.

    python3 scripts/02_render_figures.py

Which files exist is the whole configuration. Vector rather than PNG, so the
labels stay real text and scale into the report's text column. Needs Chromium
at the hardwired path below; not portable, and not trying.

The renderer is bpmn-js driven headless, the same viewer that drew the diagrams
while they were edited, so the geometry comes out of the file's own DI section.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BPMN = ROOT / 'bpmn'
OUT = BPMN / 'img'
VIEWER = ROOT / 'bpmn2petrinet/vendor/bpmn-navigated-viewer.development.js'

BROWSER = '/usr/bin/chromium'    # any Chromium-family build takes these flags
LOAD_BUDGET_MS = 15_000          # virtual time, so it is not wall-clock patience
MARGIN = 4                       # model units of white kept around the drawing
PT_PER_PX = 0.75                 # a CSS pixel is 1/96 in, a point is 1/72 in

# bpmn-js stamps a "BPMN.io" badge on every canvas: a plain DOM node, so one
# CSS rule removes it. The diagram goes in a <script type="text/xml"> block,
# which the browser stores verbatim instead of parsing.
PAGE = """<!doctype html><meta charset="utf-8">
<style>@page{{size:{w}px {h}px;margin:0}}html,body{{margin:0}}
#c{{width:{w}px;height:{h}px}}.bjs-powered-by{{display:none}}</style>
<div id="c"></div>
<script type="text/xml" id="d">
{xml}
</script>
<script>{viewer}</script>
<script>const v=new BpmnJS({{container:'#c'}});
v.importXML(document.getElementById('d').textContent)
 .then(()=>v.get('canvas').viewbox({{x:{x},y:{y},width:{w},height:{h}}}));</script>
"""

# The DI geometry read off the text rather than through a parser: these two
# shapes place everything a diagram draws, and the figures only need their
# extent. The count check in frame() keeps the shortcut honest.
BOUNDS = re.compile(r'<omgdc:Bounds x="([-\d.]+)" y="([-\d.]+)" '
                    r'width="([\d.]+)" height="([\d.]+)"')
WAYPOINT = re.compile(r'<omgdi:waypoint x="([-\d.]+)" y="([-\d.]+)"')


def frame(xml, name):
    """The rectangle the drawing occupies, labels and waypoints included.

    A shape the pattern missed would fall outside the viewbox and be cropped
    without a word, so the tags and the matches are counted and have to agree.
    """
    boxes, points = BOUNDS.findall(xml), WAYPOINT.findall(xml)
    if len(boxes) != xml.count('<omgdc:Bounds') \
            or len(points) != xml.count('<omgdi:waypoint'):
        sys.exit(f'{name}: the DI patterns missed an element, so the figure '
                 'would be cropped; check the attribute order in the file')

    xs, ys = [], []
    for x, y, w, h in boxes:
        xs += [float(x), float(x) + float(w)]
        ys += [float(y), float(y) + float(h)]
    for x, y in points:
        xs.append(float(x))
        ys.append(float(y))
    return (min(xs) - MARGIN, min(ys) - MARGIN,
            max(xs) - min(xs) + 2 * MARGIN, max(ys) - min(ys) + 2 * MARGIN)


def render(src, viewer):
    """One diagram to one PDF, and return the page size in points."""
    xml = src.read_text()
    x, y, w, h = frame(xml, src.name)
    out = OUT / f'{src.stem}.pdf'

    # Two things have to agree or the figure comes out wrong. @page must match
    # the drawing, because the browser prints on a paper size and cuts whatever
    # runs past the default Letter width. And the viewbox is set to that same
    # rectangle rather than left to fit-viewport, which frames it at 1:1.
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / 'page.html'
        page.write_text(PAGE.format(w=w, h=h, x=x, y=y,
                                    xml=xml, viewer=viewer))
        subprocess.run([BROWSER, '--headless', '--disable-gpu', '--no-sandbox',
                        '--no-pdf-header-footer',
                        f'--virtual-time-budget={LOAD_BUDGET_MS}',
                        f'--print-to-pdf={out}', page.as_uri()],
                       check=True, capture_output=True)
    return out, w * PT_PER_PX, h * PT_PER_PX


def main():
    if not Path(BROWSER).exists():
        sys.exit(f'{BROWSER} not found; edit BROWSER at the top of this script')
    if not VIEWER.exists():
        sys.exit(f'{VIEWER} not found; the README says which build to put there')
    sources = sorted(BPMN.glob('*.bpmn'))
    if not sources:
        sys.exit(f'no .bpmn under {BPMN}')

    viewer = VIEWER.read_text()
    OUT.mkdir(parents=True, exist_ok=True)
    for src in sources:
        out, width, height = render(src, viewer)
        print(f'{out.name}: {width:.0f} x {height:.0f} pt'
              f'  ({out.stat().st_size // 1024} kB)')


if __name__ == '__main__':
    main()
