---
name: tdd
description: Test-driven development with red-green-refactor loop. Use when user wants to build features or fix bugs using TDD, mentions "red-green-refactor", wants integration tests, or asks for test-first development.
---

# Test-Driven Development

## Philosophy

Tests verify behavior through public interfaces, not implementation. Code can change entirely; tests shouldn't.

**Good tests** are integration-style: they exercise real code paths through public APIs and read like a specification ("user can checkout with valid cart"). They survive refactors because they don't touch internal structure.

**Bad tests** couple to implementation — mocking internal collaborators, testing private methods, or verifying out-of-band (querying the DB instead of the interface). The tell: a rename or refactor breaks the test while behavior is unchanged.

See [TESTS.md](TESTS.md) for examples and [MOCKING.md](MOCKING.md) for mocking guidelines.

## Anti-pattern: horizontal slices

**Don't write all tests first, then all implementation.** Bulk-written tests verify *imagined* behavior — they test the *shape* of things (signatures, data structures), pass when behavior breaks, and lock in test structure before you understand the implementation.

**Vertical slices instead:** one test → one implementation → repeat. Each test responds to what the previous cycle taught you.

```
WRONG (horizontal):  RED: test1..test5   then  GREEN: impl1..impl5
RIGHT (vertical):    test1→impl1, test2→impl2, test3→impl3, ...
```

## Workflow

### 1. Planning

Explore using the project's domain glossary so test names and interface vocabulary match the project's language; respect ADRs in the area. Before any code:

- [ ] Confirm with the user the interface changes and which behaviors to test (prioritised — you can't test everything; focus on critical paths and complex logic, not every edge case)
- [ ] Identify [deep modules](DEEP-MODULES.md) and design interfaces for [testability](TESTABLE-INTERFACES.md)
- [ ] List behaviors to test (not implementation steps), and get user approval

Planning is an internal gate. Run unattended (under `auto`, entered through `pickup` on a `ready-for-agent` issue), the agent-brief stands in for that approval: take the interface and behaviors from the brief and proceed without prompting. When the brief leaves the interface or critical behaviors underspecified, wall rather than guess.

### 2. Tracer bullet

One test, one behavior, end-to-end: `RED` (test fails) → `GREEN` (minimal code passes). Proves the path works.

### 3. Incremental loop

Repeat `RED → GREEN` for each remaining behavior. One test at a time, only enough code to pass it, no anticipating future tests, always asserting observable behavior.

Run the test command in the background and read back only pass/fail plus the failing assertion — raw runner output across many cycles rots the window without adding signal.

### 4. Refactor

Only at GREEN — **never while RED**. Look for [refactor candidates](REFACTORING.md): extract duplication, deepen modules (complexity behind simple interfaces), apply SOLID where natural, act on what new code reveals about old. Re-run tests after each step.

## Checklist per cycle

```
[ ] Describes behavior, not implementation   [ ] Public interface only
[ ] Survives an internal refactor            [ ] Minimal code, no speculative features
```

## Review gate

Before opening the PR, review the branch diff:

- `/code-review` — full review: correctness bugs *and* reuse/simplification/efficiency cleanups.
- `/security-review` — security review of the pending changes.

**Required in auto, your choice in manual.** Address findings (or log them on the issue) before the PR.

Write the commit and PR prose, and any code comments, per [../../WRITING.md](../../WRITING.md) → *Commit messages*, *Code comments*: imperative subject, body says why not what, comment intent never narration.

## Handover

Per [../HANDOVER.md](../HANDOVER.md). End an interactive run by rendering this row as one `AskUserQuestion`.

- **artifact:** a tested feature (behaviors covered, GREEN), on a branch
- **default:** — (terminal; open a PR for review)
- **alternatives:** `/code-review` · `/security-review` · stop
