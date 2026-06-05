# Triage Labels

The skills speak in terms of seven canonical state roles. This file maps those roles to the actual label strings used in this repo's issue tracker. The maintainer drives the first five through `triage`; `pickup` drives the last two (the execution tail).

| Canonical role    | Label in our tracker | Meaning                                  |
| ----------------- | -------------------- | ---------------------------------------- |
| `needs-triage`    | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`      | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent` | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human` | `ready-for-human`    | Requires human implementation            |
| `wontfix`         | `wontfix`            | Will not be actioned                     |
| `in-progress`     | `in-progress`        | Claimed by `pickup`, implementation underway |
| `in-review`       | `in-review`          | PR open, awaiting human merge            |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match the vocabulary you use.
