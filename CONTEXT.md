# Claude Skills

A library of Claude Code agent skills that compose into a tracker-driven development loop. The glossary fixes the pipeline's domain terms.

## Language

**Slice**:
An independently-grabbable vertical unit of work cut from a PRD by `slice`. On the tracker it is a child of the parent PRD.
_Avoid_: ticket, subtask

**Parent**:
The PRD issue that a set of slices decompose. On the tracker it is the parent of its slices; it carries the category label only, never a readiness label.
_Avoid_: epic, umbrella issue

**PRD**:
The full multi-slice specification `spec` emits for a change that decomposes into many slices. A single-slice change skips the PRD and gets a lean agent brief instead.
_Avoid_: spec doc, design doc
