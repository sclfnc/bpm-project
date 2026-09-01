#!/usr/bin/env python3
"""Analyse every net in pnml/ with pm4py and write the answers to disk.

    .venv/bin/python scripts/04_pm4py_report.py

One <net>-report-pm4py.json per net under pnml/analysis/, and two drawings per
net under pnml/img/, for the net itself and for the graph of its reachable
markings. The pictures show the delivered net, not N*: the reset transition
belongs to the analysis and not to the model, while every number below is
measured on N*. Under three minutes for all six, the two composed nets being
the whole cost.

This is the project's only analysis, so every figure the report cites of these
six nets can be re-derived by running one command. The alternative nets the
report discusses are not among them: they were built by hand from the composed
net and measured once. The four workflow modules and the system they glue into
are treated alike, a module closed on its own interface being a workflow net
like any other.

Woflan answers most of it: soundness, liveness, boundedness and safeness, the
reachability graph and the not-well-handled pairs. Outside Woflan, pm4py gives
the incidence matrix and the workflow-net test. What is computed here, and why:

  free-choice, S-net, T-net   statements about presets and postsets, one pass
                              over the arcs; pm4py reports none of them
  free-choice violations      the checklist asks for the list, and pm4py gives
                              neither the list nor the count
  the Rank Theorem            deck 17 slide 85, four non-trivial conditions;
                              no tool in the course toolchain checks them
  S-coverability              Woflan reads it off its invariant basis, which is
                              not the set of minimal invariants, so it misses
                              components and over-reports uncovered places
  the PT/TP split of handles  Woflan returns one undifferentiated list, and the
                              course states well-structuredness on the two
                              kinds separately

Everything else is Woflan's own answer, kept verbatim.
"""
import json
import re
import sys
from pathlib import Path

# pm4py prints an AGPL banner on import, to stderr; it never reaches a report.
import networkx as nx
import numpy as np
import pm4py
from scipy.optimize import linprog
from pm4py.algo.analysis.woflan import algorithm as woflan
from pm4py.algo.analysis.woflan.not_well_handled_pairs \
    import not_well_handled_pairs as nwh
from pm4py.objects.petri_net.obj import Marking, PetriNet
from pm4py.objects.petri_net.utils import (incidence_matrix, networkx_graph,
                                           reachability_graph)

ROOT = Path(__file__).resolve().parent.parent
PNML = ROOT / 'pnml'
OUT = PNML / 'analysis'
IMG = PNML / 'img'


# --------------------------------------------------------------------------
# Reading pm4py back
# --------------------------------------------------------------------------

def diag_get(diagnostics, output, default=None):
    """One entry of Woflan's diagnostics, whichever way pm4py filed it.

    pm4py keys most entries by `Outputs.X.value`, a plain string, and two by
    the enum member itself (`woflan/algorithm.py:275` and `:280`), so both are
    tried.
    """
    if output in diagnostics:
        return diagnostics[output]
    return diagnostics.get(output.value, default)


def is_place(node):
    """A node's class is what tells a place from a transition once it is out
    of the set it belongs to."""
    return isinstance(node, PetriNet.Place)


# --------------------------------------------------------------------------
# Handles, and the PT/TP split Woflan does not make
# --------------------------------------------------------------------------

def handles(net):
    """The not-well-handled pairs, named and split into PT and TP.

    pm4py returns pairs of integers into a doubled graph: every node has an
    even index for its input copy and the odd successor for its output copy.
    Reading `apply` (`not_well_handled_pairs.py:77-90`), the two shapes it
    appends are

        (booking[place] + 1,      booking[transition])   a PT-handle
        (booking[transition] + 1, booking[place])        a TP-handle

    The bookkeeping is rebuilt here because `apply` does not return it, and its
    numbering follows set iteration order, so each pair is matched against
    those shapes before it is classified.
    """
    _, booking = nwh.create_network_graph(net)
    node_at = {index: node for node, index in booking.items()}
    pt, tp = [], []
    for tail, head in nwh.apply(net):
        source, target = node_at[tail - 1], node_at[head]
        if is_place(source) and not is_place(target):
            pt.append((source.name, target.name))
        elif not is_place(source) and is_place(target):
            tp.append((source.name, target.name))
        else:
            sys.exit('a not-well-handled pair joins two nodes of the same kind: '
                     "pm4py's bookkeeping no longer matches its output")
    return sorted(pt), sorted(tp)


# --------------------------------------------------------------------------
# Structure: everything decided by presets and postsets
# --------------------------------------------------------------------------

def structure(net):
    """The structural checks, all decided by one pass over the arcs.

    Free-choice, S-net and T-net are the three no tool in the course toolchain
    reports; the rest are WoPeD's expert panel.
    """
    pre = {t: {a.source for a in t.in_arcs} for t in net.transitions}
    post = {t: {a.target for a in t.out_arcs} for t in net.transitions}
    transitions = sorted(net.transitions, key=lambda x: x.name)
    places = sorted(net.places, key=lambda x: x.name)

    # Free-choice: any two transitions have equal or disjoint presets. The
    # checklist asks for the offending pairs with the places they share, which
    # is also what locates the deferred choices.
    violations = [{'transitions': [a.name, b.name],
                   'shared_places': sorted(p.name for p in pre[a] & pre[b])}
                  for i, a in enumerate(transitions) for b in transitions[i + 1:]
                  if pre[a] & pre[b] and pre[a] != pre[b]]

    # S-net and T-net are the same condition, one input and one output, read on
    # the two kinds of node.
    offending_transitions = [t.name for t in transitions
                             if len(pre[t]) != 1 or len(post[t]) != 1]
    offending_places = [p.name for p in places
                        if len(p.in_arcs) != 1 or len(p.out_arcs) != 1]

    # Names index the S-component subnets built elsewhere in this script, so a
    # place and a transition sharing one would merge two vertices there. Refuse.
    names = [n.name for n in net.places] + [n.name for n in net.transitions]
    if len(names) != len(set(names)):
        sys.exit('two nodes share a name: the S-component subnets would merge them')
    graph, _ = networkx_graph.create_networkx_directed_graph(net)

    return {
        'free_choice': not violations,
        'conflicting_pairs': len(violations),
        'free_choice_violations': violations,
        's_net': not offending_transitions,
        'transitions_not_one_in_one_out': offending_transitions,
        't_net_on_short_circuit': not offending_places,
        'places_not_one_in_one_out': offending_places,
        'transitions_with_empty_preset':
            [t.name for t in transitions if not pre[t]],
        'transitions_with_empty_postset':
            [t.name for t in transitions if not post[t]],
        'arcs_with_non_standard_weight':
            [f'{a.source.name} -> {a.target.name}' for a in net.arcs
             if getattr(a, 'weight', 1) != 1],
        'connected_components_of_short_circuit':
            nx.number_weakly_connected_components(graph),
        'strongly_connected_components_of_short_circuit':
            nx.number_strongly_connected_components(graph),
    }


# --------------------------------------------------------------------------
# Behaviour: the reachable markings, and what they settle
# --------------------------------------------------------------------------

def reachable_markings(net, im):
    """Enumerate the reachable markings, and build the graph from them.

    Calling the two halves of `construct_reachability_graph`
    (`reachability_graph.py:167-192`) keeps the markings, which the one-shot
    call turns into node labels and discards. `marking_flow_petri` returns what
    it has if it gives up, so every marking recorded as reachable is checked to
    have been expanded too.
    """
    incoming, outgoing, _ = reachability_graph.marking_flow_petri(net, im)
    unexpanded = set(incoming) - set(outgoing)
    if unexpanded:
        sys.exit(f'the marking flow stopped early with {len(unexpanded)} marking(s) '
                 'unexpanded: the state space is larger than it reports')
    graph = reachability_graph.construct_reachability_graph_from_flow(
        incoming, outgoing)
    return list(incoming), graph


# --------------------------------------------------------------------------
# The Rank Theorem
# --------------------------------------------------------------------------

def clusters(net):
    """How many clusters the net has.

    The course defines a node's cluster as the least set containing it and
    closed under two rules, a place dragging in its postset and a transition
    its preset (deck 17, slides 88-90). Both relate a place to a transition
    across an arc leaving the place, so the clusters are the classes of the
    equivalence those arcs generate. Nodes are keyed by (kind, name), so a
    place and a transition sharing one stay apart.
    """
    parent = {}

    def find(x):
        while parent[x] != x:                   # path halving, so repeated
            parent[x] = parent[parent[x]]       # lookups stay near-constant
            x = parent[x]
        return x

    for place in net.places:
        parent[('p', place.name)] = ('p', place.name)
    for transition in net.transitions:
        parent[('t', transition.name)] = ('t', transition.name)
    for arc in net.arcs:
        if is_place(arc.source):
            a, b = find(('p', arc.source.name)), find(('t', arc.target.name))
            if a != b:
                parent[a] = b
    return len({find(node) for node in parent})


def unmarked_siphon(net, marking):
    """The largest siphon the marking leaves empty.

    The course gives the algorithm (deck 17, slide 105): start from the unmarked
    places and drop any place fed by a transition that takes nothing from the
    set, until nothing more can be dropped. What survives contains every
    unmarked siphon, so an empty result is the theorem's third condition.
    """
    siphon = {p for p in net.places if marking[p] == 0}
    shrinking = True
    while shrinking:
        shrinking = False
        fed_by_siphon = {a.target for p in siphon for a in p.out_arcs}
        for place in list(siphon):
            if {a.source for a in place.in_arcs} - fed_by_siphon:
                siphon.discard(place)
                shrinking = True
    return sorted(p.name for p in siphon)


def incidence(net):
    """The incidence matrix as integer rows, one per place, from pm4py.

    `incidence_matrix.construct` orders places and transitions by name and
    accumulates arc contributions, so a self-loop cancels to zero as the
    definition requires. It reads every arc as weight one, so a weighted net is
    refused rather than answered about.
    """
    odd = [a for a in net.arcs if (getattr(a, 'weight', 1) or 1) != 1]
    if odd:
        sys.exit(f'{len(odd)} arc(s) carry a weight: pm4py builds the matrix '
                 f'with unit entries and would answer about another net')
    return incidence_matrix.construct(net).a_matrix


def rank(matrix):
    """Exact rank, by Bareiss fraction-free elimination.

    Every intermediate value is a minor of the original integer matrix, so it
    stays an integer and the division is exact. The theorem compares this number
    against a count of clusters, where being off by one is the whole answer.
    """
    a = [row[:] for row in matrix]
    rows = len(a)
    cols = len(a[0]) if rows else 0
    pivot_row, previous = 0, 1
    for c in range(cols):
        pivot = next((i for i in range(pivot_row, rows) if a[i][c]), None)
        if pivot is None:                       # column already dependent
            continue
        a[pivot_row], a[pivot] = a[pivot], a[pivot_row]
        for i in range(pivot_row + 1, rows):
            for j in range(c + 1, cols):
                a[i][j] = (a[i][j] * a[pivot_row][c]
                           - a[i][c] * a[pivot_row][j]) // previous
            a[i][c] = 0
        previous = a[pivot_row][c]
        pivot_row += 1
    return pivot_row


def has_positive_kernel_vector(matrix):
    """Is there a strictly positive v with matrix times v equal to zero?

    The one floating-point step here. The program asks for v >= 1 rather than
    v > 0: the same question over the rationals, since any solution scales, and
    a closed region an LP can decide.
    """
    n = len(matrix[0]) if matrix else 0
    solution = linprog(c=np.zeros(n),
                       A_eq=np.array(matrix, dtype=float),
                       b_eq=np.zeros(len(matrix)),
                       bounds=[(1, None)] * n,
                       method='highs')
    return bool(solution.success)


def s_cover(net):
    """The places that lie in no S-component, decided one place at a time.

    Woflan derives its S-components from an invariant basis, and a basis is not
    the set of minimal invariants, so a place can sit in a component no basis
    vector names. On the collaboration it reports ten uncovered places where
    four are, and on the variant two where none are.

    The question is put directly instead. For a place p, is there a set S of
    places containing p such that every transition touching S has exactly one
    input and one output place in S, and the subnet S induces is strongly
    connected? The first two conditions are an integer program over 0/1 place
    variables, one equation per transition and at most one input place in S;
    minimising its size leaves the connectivity test something small to
    confirm.
    """
    places = sorted(net.places, key=lambda x: x.name)
    index = {p: i for i, p in enumerate(places)}
    pre = {t: [a.source for a in t.in_arcs] for t in net.transitions}
    post = {t: [a.target for a in t.out_arcs] for t in net.transitions}
    transitions = sorted(net.transitions, key=lambda x: x.name)

    equations, inputs = [], []
    for t in transitions:
        balance = np.zeros(len(places))
        entering = np.zeros(len(places))
        for q in pre[t]:
            balance[index[q]] += 1
            entering[index[q]] += 1
        for q in post[t]:
            balance[index[q]] -= 1
        equations.append(balance)
        inputs.append(entering)
    equations = np.array(equations)
    inputs = np.array(inputs)

    uncovered = []
    for p in places:
        bounds = [(0, 1)] * len(places)
        bounds[index[p]] = (1, 1)
        solution = linprog(c=np.ones(len(places)),
                           A_ub=inputs, b_ub=np.ones(len(transitions)),
                           A_eq=equations, b_eq=np.zeros(len(transitions)),
                           bounds=bounds,
                           integrality=np.ones(len(places)),
                           method='highs')
        if not solution.success:
            uncovered.append(p.name)
            continue
        component = {places[i] for i, v in enumerate(solution.x) if v > 0.5}
        touching = [t for t in transitions
                    if set(pre[t]) & component or set(post[t]) & component]
        graph = nx.DiGraph()
        for t in touching:
            for q in set(pre[t]) & component:
                graph.add_edge(q.name, t.name)
            for q in set(post[t]) & component:
                graph.add_edge(t.name, q.name)
        one_in_one_out = all(len(set(pre[t]) & component) == 1
                             and len(set(post[t]) & component) == 1
                             for t in touching)
        # The program constrains the arcs and not the connectivity, so a
        # solution could be a disjoint union. Refuse rather than answer about a
        # set that is not a component.
        if not (one_in_one_out and nx.is_strongly_connected(graph)):
            sys.exit(f'{p.name}: the minimal solution is not an S-component')
    return {'s_coverable': not uncovered,
            'places_in_no_s_component': uncovered}


def rank_theorem(net, marking):
    """The four non-trivial conditions of the Rank Theorem, checked on N*.

    The course states it in six (deck 17, slide 85); non-emptiness and
    connectedness are the trivial two, and `structure` reports the second. The
    six are equivalent to live and bounded for a free-choice system, which on a
    workflow net is soundness. On a net that is not free-choice they conclude
    nothing, so the caller records free-choice beside them.

    An S-invariant is a left kernel vector of the incidence matrix and a
    T-invariant a right kernel vector, so one function serves both.
    """
    matrix = incidence(net)
    transpose = [list(column) for column in zip(*matrix)]
    siphon = unmarked_siphon(net, marking)
    r, k = rank(matrix), clusters(net)
    return {
        'every_proper_siphon_marked': not siphon,
        'largest_unmarked_siphon': siphon,
        'positive_s_invariant': has_positive_kernel_vector(transpose),
        'positive_t_invariant': has_positive_kernel_vector(matrix),
        'rank_of_incidence_matrix': r,
        'clusters': k,
        'rank_equals_clusters_minus_one': r == k - 1,
    }


# --------------------------------------------------------------------------
# One net, end to end
# --------------------------------------------------------------------------

def draw(net, im, fm, graph, stem):
    """The two pictures, each named for what it shows.

    Both show the delivered net: the reachability graph drawn here is the one
    reachable from the initial marking without the reset transition, so it has
    one arc fewer than the graph of N* the report measures.

    Vector and not raster: Graphviz truncates a PNG at 32767 pixels, which the
    composition's reachability graph is far past. Drawing needs `dot` on PATH
    and the analysis does not.
    """
    drawn = {}
    renderers = (
        ('pnml', lambda f: pm4py.save_vis_petri_net(net, im, fm, f)),
        ('reachability', lambda f: pm4py.save_vis_transition_system(graph, f)),
    )
    for kind, call in renderers:
        relative = f'img/{stem}-{kind}-pm4py.pdf'
        try:
            call(str(PNML / relative))
            drawn[kind] = relative
        except Exception as exc:
            print(f'  {stem} {kind}: not drawn ({type(exc).__name__})',
                  file=sys.stderr)
            drawn[kind] = None
    return drawn


# One message lists not-well-handled pairs by internal index. Those indices
# follow set iteration order and name nothing a reader can look up, so that one
# is summarised; every other message is left as Woflan wrote it.
UNSTABLE = re.compile(r'^(Not well-handled pairs are: )\[.*\]\.?\s*$', re.S)


def stabilise(message):
    """Woflan's own words, with its one unreproducible list summarised."""
    match = UNSTABLE.match(message)
    if not match:
        return message
    return (f'{match.group(1)}{message.count("(")} pairs. The indices pm4py '
            'prints here are internal and differ between runs, so they are '
            'omitted; the pairs are named in the JSON.')


def analyse(path):
    """Every answer about one net, as the dict the JSON report is written from.

    It is assembled in four blocks, one per source: the file, Woflan, pm4py
    outside Woflan, and this script. The last block holds only what none of the
    other three answers.
    """
    net, im, fm = pm4py.read_pnml(str(path))
    # The converter writes no final marking, so it is the sink holding one
    # token, which is what proper completion means for a workflow net.
    if not fm:
        sinks = [p for p in net.places if not p.out_arcs]
        if len(sinks) != 1:
            sys.exit(f'{path.name}: {len(sinks)} sinks, expected one')
        fm = Marking({sinks[0]: 1})

    # The enumeration here serves one purpose, the picture of the delivered
    # net, which needs a transition system Woflan does not hand back. It is
    # also the count Woflan's own graph is checked against below.
    _, graph = reachable_markings(net, im)
    images = draw(net, im, fm, graph, path.stem)

    # Early exit is off so that an unsound net still yields every diagnostic
    # rather than the first failing one.
    sound, diagnostics = woflan.apply(net, im, fm, parameters={
        woflan.Parameters.RETURN_ASAP_WHEN_NOT_SOUND: False,
        woflan.Parameters.PRINT_DIAGNOSTICS: False,
        woflan.Parameters.RETURN_DIAGNOSTICS: True})
    out = woflan.Outputs

    # N* and the reachability graph are Woflan's own objects, so the structural
    # answers below are about the net Woflan analysed.
    star = diag_get(diagnostics, out.S_C_NET)
    rg = diag_get(diagnostics, out.R_G_S_C)
    if star is None or rg is None:
        sys.exit(f'{path.name}: Woflan returned no short circuit or no graph')
    # The enumeration above and Woflan's graph must agree.
    if rg.number_of_nodes() != len(graph.states):
        sys.exit(f'{path.name}: Woflan counts {rg.number_of_nodes()} markings, '
                 f'this script {len(graph.states)}')

    # Woflan's N* is a fresh object, so the initial marking is carried over by
    # name; the one keyed on this net's places would leave N* unmarked.
    by_name = {q.name: q for q in star.places}
    star_im = Marking({by_name[str(q)]: k for q, k in im.items()})

    # Safeness is read off the markings Woflan stores on each node, as a vector
    # over its places in name order.
    star_places = sorted(star.places, key=lambda x: x.name)
    peak = {q.name: 0 for q in star_places}
    for node in rg.nodes:
        for i, count in enumerate(rg.nodes[node]['marking']):
            peak[star_places[i].name] = max(peak[star_places[i].name],
                                            int(count))

    # Twice: the course states well-structuredness on N*, and the difference
    # between the two counts is what the closure costs.
    pt_open, tp_open = handles(net)
    pt_star, tp_star = handles(star)

    return {
        # -- the file ----------------------------------------------------
        'net': path.name,
        'images': images,
        'places': len(net.places),
        'transitions': len(net.transitions),
        'arcs': len(net.arcs),
        'source_places': [p.name for p in net.places if not p.in_arcs],
        'sink_places': [p.name for p in net.places if not p.out_arcs],
        'initial_marking': {str(p): n for p, n in im.items()},
        'final_marking': {str(p): n for p, n in fm.items()},

        # -- Woflan ------------------------------------------------------
        'sound': bool(sound),
        'reachability_graph_states_on_short_circuit': rg.number_of_nodes(),
        'reachability_graph_transitions_on_short_circuit': rg.number_of_edges(),
        # Liveness is the strong connectivity of that graph, the criterion
        # Woflan applies at `algorithm.py:690` and then reports only in prose.
        'live_on_short_circuit': bool(nx.is_strongly_connected(rg)),
        'bounded': True,                # Woflan's graph is finite, so it is
        'safe': max(peak.values()) == 1,
        'max_tokens_in_any_place': max(peak.values()),
        'places_holding_more_than_one_token':
            sorted(p for p, n in peak.items() if n > 1),
        'dead_tasks':
            sorted(str(t) for t in diag_get(diagnostics, out.DEAD_TASKS, [])),
        'deadlock_scenarios':
            len(diag_get(diagnostics, out.LOCKING_SCENARIOS, []) or []),
        'pt_handles_open': len(pt_open),
        'tp_handles_open': len(tp_open),
        'pt_handles_short_circuit': len(pt_star),
        'tp_handles_short_circuit': len(tp_star),
        'pt_handle_pairs_short_circuit': pt_star,
        'tp_handle_pairs_short_circuit': tp_star,
        'messages': [stabilise(str(m).replace('\n', ' ')) for m in
                     diag_get(diagnostics, out.DIAGNOSTIC_MESSAGES, [])],

        # -- pm4py, outside Woflan ---------------------------------------
        'workflow_net': bool(pm4py.check_is_workflow_net(net)),

        # -- computed here, because nothing in pm4py answers them --------
        **structure(star),
        **s_cover(star),
        'rank_theorem': rank_theorem(star, star_im),
    }


def main():
    nets = sorted(PNML.glob('*.pnml'))
    if not nets:
        sys.exit(f'no .pnml under {PNML}: run scripts/03_to_pnml.py first')
    OUT.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    for path in nets:
        r = analyse(path)
        (OUT / f'{path.stem}-report-pm4py.json').write_text(
            json.dumps(r, indent=2) + '\n')
        print(f"{path.stem:30s} sound={str(r['sound']):5s} "
              f"{r['places']}/{r['transitions']}/{r['arcs']}  "
              f"|V|={r['reachability_graph_states_on_short_circuit']}  "
              f"handles N* {r['pt_handles_short_circuit']}"
              f"/{r['tp_handles_short_circuit']}")
    print(f'\nwritten: {len(nets)} files in {OUT.relative_to(ROOT)}/')


if __name__ == '__main__':
    main()
