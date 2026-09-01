# P29 "Thesis": Business Process Modelling project

- Project report for the Business Process Modelling course
- MSc in Data Science and Business Informatics
- Università di Pisa
- Academic Year 2025/2026.

## What this is

The assignment (`p29-Tesi-it-Secoli.pdf`) describes a thesis-preparation scenario and asks for models at an abstract level, their translation into workflow nets, and an analysis of those nets. 

It is organized as follows:

1. **Scenario.** The decisions that close the gaps the brief leaves open, and where each requirement is discharged.
2. **Models.** The collaboration, its four pools and 27 message flows, and how the nets were obtained.
3. **Analysis.** The pool nets are safe and sound; the composition is not.

It fails three ways, soundness, weak soundness and relaxed soundness, and all three trace to one specific deadlock that Section 3 identifies and argues.

Every number the report analyses comes from `pnml/analysis/`, from a count taken off `bpmn/*.bpmn`, or from an arithmetic derivation printed beside it, tool versions and the title block excepted.

## Layout

| Path | What it holds |
|---|---|
| `bpmn/` | The six diagrams. Only `collaboration.bpmn` is edited by hand; `collaboration-no-withdrawal.bpmn` is rebuilt by nothing, see the trap below. |
| `bpmn/img/` | One vector PDF per diagram. The report prints `collaboration.pdf` only. |
| `pnml/` | The six workflow nets. `pnml/README.md` records the two schema repairs step 3 applies. |
| `pnml/analysis/` | One JSON report per net. No text report is produced. |
| `pnml/img/` | Two drawings per net, plus six `-woped.png` exported by hand from WoPeD. The report prints none of the eighteen. |
| `scripts/` | The four numbered scripts, and the bpmnlint harness under `lint/`. |
| `LaTeX/` | The source of the report. `main.pdf` is built from here into the project root. |

## Third-party code that is not here

Steps 2 and 3 need the converter, and this repository does not carry it. Pull it from GitHub into a folder named `bpmn2petrinet` at the project root, the path both scripts read, and build the two files the viewer needs:

```sh
git clone --depth 1 https://github.com/BenjaNapo/bpmn-to-petri.git bpmn2petrinet
mkdir bpmn2petrinet/vendor
cp bpmn2petrinet/node_modules/jquery/dist/jquery.min.js \
   bpmn2petrinet/vendor/jquery-3.7.1.min.js
sed '13s|^export default ||' \
   bpmn2petrinet/node_modules/bpmn-js/dist/bpmn-navigated-viewer.development.js \
   > bpmn2petrinet/vendor/bpmn-navigated-viewer.development.js
```

- **What it is.** [bpmn-to-petri](https://github.com/BenjaNapo/bpmn-to-petri) by Andrea Napolitano and Roberto Bruni (University of Pisa), MIT licensed, at commit `676f2b3`. Step 3 reads only the nine modules under `src/bpmn2petri/`, none of the rest of the 91 MB clone.
- **Why the `sed`.** Line 13 of the vendored **bpmn-js 18.1.2** carries an `export default` that the classic `<script>` block of step 2 cannot parse. Skip the patch and step 2 exits 0 while writing six blank PDFs of about 850 bytes, which is the only signal you get.

The converter also has an interactive page, live at <https://bpmn2petrinet.com/>. We drive it headless instead, so the six diagrams convert in one command.

## Recreating every file

Everything under `bpmn/` and `pnml/` follows from `bpmn/collaboration.bpmn`, in this order, run from the project root.

```sh
# 0. the two environments, built once each
python3 -m venv .venv                          # for script 4
.venv/bin/pip install -r scripts/requirements.txt
npm ci --prefix scripts/lint                   # for the linter    [needs Node]

# 1. split the collaboration into the four standalone pool diagrams
python3 scripts/01_extract_pools.py            # -> bpmn/{student,supervisor,counter-examiner,committee}.bpmn

# a check rather than a step: validate all six diagrams
npm --prefix scripts/lint run lint             # silence and exit 0 mean no findings

# 2. export every diagram to a vector PDF                    [needs Chromium]
python3 scripts/02_render_figures.py           # -> bpmn/img/*.pdf

# 3. convert every diagram to a workflow net                 [needs Chromium]
python3 scripts/03_to_pnml.py                  # -> pnml/*.pnml

# 4. Woflan and the structural analysis on every net    [Graphviz optional]
.venv/bin/python scripts/04_pm4py_report.py    # -> pnml/analysis/*-report-pm4py.json

# 5. the report
cd LaTeX && latexmk -pdf main.tex              # -> main.pdf
```

| For | Needs |
|---|---|
| Scripts 01 to 03 | Python 3.9 or later. Standard library only |
| Script 04 | The `.venv` above. `requirements.txt` pins nothing, and the delivered JSON came from pm4py 2.7.23.6 on Python 3.13.5, so byte-identity holds only there |
| Diagram validation | Node with `npm`. The lockfile pins bpmnlint 11.12.1 by version and hash |
| Steps 2 and 3 | Chromium: both scripts hardwire `/usr/bin/chromium` |
| The drawings step 4 saves | Graphviz on `PATH`; without it the analysis still runs |
| The report | TeX Live with `latexmk` |

- **The trap.** No step rebuilds `bpmn/collaboration-no-withdrawal.bpmn`, derived once with a script we no longer have, so any edit to the collaboration leaves it silently stale: re-derive it by hand, then re-run steps 2 to 4. Everything else keeps itself in step, since steps 2 and 3 read whatever `.bpmn` they find and step 4 reads `pnml/` the same way.
- **Provenance.** Woflan supplies soundness, the reachability graph of the short-circuit net, dead tasks and locking scenarios. Everything else in the JSON, the structural verdicts and the S-coverability, is computed by `scripts/04_pm4py_report.py` itself.

## Building the report

`LaTeX/` needs `bpmn/img/collaboration.pdf` from step 2. Every number in its tables was transcribed from `pnml/analysis/*.json` by hand, with nothing enforcing the agreement, and `.latexmkrc` explains in its own comments why it pins pdfTeX and where it sends the PDF.

## Known limits

1. **Woflan over-reports uncovered places.** On the collaboration it names ten where the true answer is four. Do not quote its S-coverability answer, nor the two invariant-coverage messages in the same code path; the report solves an exact integer program per place instead.
2. **pm4py warns about scipy.** Every run of step 4 prints it and suggests installing PuLP. That path feeds those same messages, and the script's own answers do not use it.
3. **Three claims are asserted, not derived.** The no-withdrawal variant's safeness and reachability-graph size, its handle counts, and the pools' free-choice property and T-invariant. All three hold against the delivered JSON.
4. **Figure 1 is small.** The collaboration is too wide to scale to the line width without shrinking its labels, and its four phases are too unequal to cut into separate figures. It ships as one strip.

---

> Readme created and revised with the help of Claude Code
