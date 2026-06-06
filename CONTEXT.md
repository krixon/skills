# Context

Domain glossary for the skills library. Engineering skills read this vocabulary and use it in the prose they leave behind; add a term here when a word carries a specific, load-bearing meaning in this project.

## Glossary

**Primary working tree** — The original clone's checkout, the one a human sits in. It holds at most one active branch at a time; work that can't take that slot is isolated in a separate worktree. *Avoid*: main checkout, root repo.

**Occupied** — The state of the primary working tree when its single slot is taken — it is not clean-on-the-default-branch, so a newly-started task must be worktree-isolated instead. The complement, free, is the only state in which the primary tree may be taken for new work. *Avoid*: busy, in use, dirty.

**Active branch** — The branch a working tree currently has checked out and is committing to. The primary tree's invariant is one active branch: the solo, sequential occupant kept there for visibility. *Avoid*: current branch, working branch.
