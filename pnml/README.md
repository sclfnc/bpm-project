# The workflow nets, and how ProM reads them

`student.pnml`, `supervisor.pnml`, `counter-examiner.pnml` and `committee.pnml` are the four orchestrations, `collaboration.pnml` is the composition, and `collaboration-no-withdrawal.pnml` is a hypothetical variant. All six are written by `scripts/03_to_pnml.py`. `analysis/` holds what the tools answered and `img/` what they drew.

## What was done to make ProM read these files

bpmn2petrinet writes a `<position>` inside every annotation's `<graphics>`, where PNML wants an `<offset>`: a position belongs to a node's graphics, an offset to an annotation's. WoPeD reads the file anyway; ProM validates and returns
    
>    ```
>    InSufficientResultException: Plugin Import Petri net from PNML file
>    produced 0 results, while 2 results were declared.
>    ```

`scripts/03_to_pnml.py` renames them and gives the net the `id` and `type` the standard asks for. With that, all six files import, the four pool nets included, which never did before. Anything downloaded from <https://bpmn2petrinet.com/> needs the same repair:

```python
re.sub(r'<name>.*?</name>',
       lambda m: m.group(0).replace('<position ', '<offset '),
       pnml, flags=re.S)
```

## Running the analysis by hand

The pipeline puts the question to pm4py's Woflan from the command line, but the course's checklist names ProM and the same analysis runs there: open the file with the **PNML Petri net files** importer, not the accepting-net one, and run **Analyze with Woflan**. It takes about sixteen minutes on the composed net and reports names rather than counts, so its lists have to be counted by hand, and unlabelled places and transitions render as blank lines. Where the two can be compared they agree.
