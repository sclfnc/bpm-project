#!/usr/bin/env python3
"""Rebuild the four standalone pool files from collaboration.bpmn.

    python3 scripts/01_extract_pools.py

collaboration.bpmn is the source of truth, so the pool files are never edited
by hand. Each output is self-contained: the pool's process, the messages it
references, a one-participant collaboration so the frame still draws, and its
diagram elements moved to the top-left.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BPMN = Path(__file__).resolve().parent.parent / 'bpmn'
SRC = BPMN / 'collaboration.bpmn'

# Semantics, drawing layer, bounds and waypoints. Registering them keeps the
# bpmn:/bpmndi: prefixes instead of ns0:/ns1:, which is what lets bpmn.io
# reopen the files.
NS = {'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
      'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
      'omgdc': 'http://www.omg.org/spec/DD/20100524/DC',
      'omgdi': 'http://www.omg.org/spec/DD/20100524/DI'}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
B, DI = '{%s}' % NS['bpmn'], '{%s}' % NS['bpmndi']
DC, OD = '{%s}' % NS['omgdc'], '{%s}' % NS['omgdi']

# process id -> output file, participant id, pool label
POOLS = {'Proc_S': ('student.bpmn', 'Part_S', 'Student'),
         'Proc_D': ('supervisor.bpmn', 'Part_D', 'Supervisor'),
         'Proc_C': ('counter-examiner.bpmn', 'Part_C', 'Counter-examiner'),
         'Proc_K': ('committee.bpmn', 'Part_K', 'Committee')}

HEADER = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<!-- AUTO-EXTRACTED from collaboration.bpmn.'
          ' Edit the collaboration and re-run scripts/01_extract_pools.py. -->\n')

# Frame origin, the strip carrying the pool name, and the margin around it.
POOL_X, POOL_Y = 150, 80
HEAD, PAD = 30, 20


def coords(element):
    """Every Bounds and waypoint under a diagram element, nested labels included.

    iter() rather than find(): an external label's Bounds sits inside
    <bpmndi:BPMNLabel>, one level below the shape's own. Reading direct
    children only would move the shapes and strand the labels hundreds of
    pixels away, at their collaboration coordinates.
    """
    yield from element.iter(f'{DC}Bounds')
    yield from element.iter(f'{OD}waypoint')


def extract(root, messages, plane, pid, fname, part_id, label):
    """Write one pool file, and return the size of the frame it drew."""
    process = next(p for p in root.findall(f'{B}process') if p.get('id') == pid)

    # Selecting by membership in the process drops the message flows for free:
    # they belong to the collaboration, and a lone pool has no partner left.
    owned = {el.get('id') for el in process if el.get('id')}
    diagram = [shape for shape in plane if shape.get('bpmnElement') in owned]
    if not diagram:
        sys.exit(f'{pid}: no diagram elements found; check the process id')

    # The collaboration stacks the pools down a tall canvas, so raw coordinates
    # would open one far below an empty page. Measure and move to the top-left.
    xs, ys = [], []
    for shape in diagram:
        for box in coords(shape):
            x, y = float(box.get('x')), float(box.get('y'))
            xs += [x, x + float(box.get('width', 0))]
            ys += [y, y + float(box.get('height', 0))]

    # Round the offset, never the coordinates: adding an integer preserves the
    # relative geometry, so an arrowhead on a gateway vertex stays on it.
    dx = round(POOL_X + HEAD + PAD - min(xs))
    dy = round(POOL_Y + PAD - min(ys))
    for shape in diagram:
        for box in coords(shape):
            box.set('x', f"{float(box.get('x')) + dx:g}")
            box.set('y', f"{float(box.get('y')) + dy:g}")
    width = round(max(xs) - min(xs)) + HEAD + 2 * PAD
    height = round(max(ys) - min(ys)) + 2 * PAD

    definitions = ET.Element(f'{B}definitions',
                             {'id': f'Definitions_{pid}',
                              'targetNamespace': 'http://bpmn.io/schema/bpmn'})

    # Only the messages this pool's events point at: copying all of them would
    # leave definitions nothing references, which an editor reports as dangling.
    referenced = {e.get('messageRef') for e in process.iter()
                  if e.get('messageRef')}
    definitions.extend(m for m in messages if m.get('id') in referenced)

    # A process on its own renders as a bare flow. Wrapping it in a
    # collaboration of one participant is what draws the labelled pool.
    collaboration = ET.SubElement(definitions, f'{B}collaboration',
                                  {'id': f'Collab_{pid}'})
    ET.SubElement(collaboration, f'{B}participant',
                  {'id': part_id, 'name': label, 'processRef': pid})

    # These reuse the parsed source's own elements. ElementTree lets an element
    # hang under two parents, and the source is never written back.
    definitions.append(process)

    diagram_root = ET.SubElement(definitions, f'{DI}BPMNDiagram',
                                 {'id': f'Diag_{pid}'})
    pool_plane = ET.SubElement(diagram_root, f'{DI}BPMNPlane',
                               {'id': f'Plane_{pid}',
                                'bpmnElement': f'Collab_{pid}'})
    frame = ET.SubElement(pool_plane, f'{DI}BPMNShape',
                          {'id': f'di_{part_id}', 'bpmnElement': part_id,
                           'isHorizontal': 'true'})
    ET.SubElement(frame, f'{DC}Bounds',
                  {'x': str(POOL_X), 'y': str(POOL_Y),
                   'width': str(width), 'height': str(height)})
    pool_plane.extend(diagram)

    body = ET.tostring(definitions, encoding='unicode')
    (BPMN / fname).write_text(HEADER + body + '\n')
    return width, height


def main():
    if not SRC.exists():
        sys.exit(f'{SRC} not found')
    root = ET.parse(SRC).getroot()
    messages = root.findall(f'{B}message')
    plane = root.find(f'.//{DI}BPMNPlane')
    if plane is None:
        sys.exit(f'{SRC.name}: no BPMNPlane, so there is no diagram to split')

    for pid, (fname, part_id, label) in POOLS.items():
        width, height = extract(root, messages, plane, pid, fname, part_id, label)
        print(f'{fname}: pool {width}x{height}')


if __name__ == '__main__':
    main()
