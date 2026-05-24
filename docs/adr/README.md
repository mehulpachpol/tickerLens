# ADRs (Architecture Decision Records)

We store short decision notes in this folder so that *why* we built something is always clear.

## Format

- Filename: `NNNN-short-title.md` (e.g., `0001-record-architecture-decisions.md`)
- Sections:
  - Context
  - Decision
  - Consequences

## When to add an ADR

- Picking or changing a core component (DB, vector store, search engine, scheduler, queue)
- Changing data model semantics (document ids, versioning rules, chunk lineage)
- Non-trivial tradeoffs (speed vs accuracy, simplicity vs scalability)

