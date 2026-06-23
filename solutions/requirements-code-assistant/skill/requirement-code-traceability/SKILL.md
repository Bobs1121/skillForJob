---
name: requirement-code-traceability
description: Retrieve atomic requirements with source evidence, compare requirements against an indexed codebase, report implementation and verification gaps, and produce implementation plans. Use when an agent must answer what a feature requires, check whether code matches a specification, trace a requirement to symbols or tests, or plan a feature change using a requirements vault plus CodeGraph.
---

# Requirement-Code Traceability

Use two evidence sources:

- Requirements MCP: reviewed atomic requirements, source version, section, and page.
- Code MCP: symbols, callers/callees, impact, and scoped task context.

Never treat semantic similarity as proof of implementation.

## Answer a requirement question

1. Call `requirements_search` with the user's wording.
2. Call `requirements_get` for the best matching IDs.
3. Return conditions, parameters, outputs, exceptions, source version, and pages.
4. State coverage limits when the source document is only partially atomized.

## Check requirement-to-code consistency

1. Load the complete atomic requirement.
2. Search each parameter, state transition, input, output, and suppression condition separately.
3. Use `code_search`, then inspect callers/callees or impact where relevant.
4. Compare field by field; use only `matched`, `mismatch`, `missing`, or `unknown`.
5. Report verification independently as `unverified`, `partial`, `verified`, or `failed`.

Read [comparison-rules.md](references/comparison-rules.md) before a formal consistency assessment.

## Produce an implementation plan

1. Retrieve related requirements, including shared suppression, fault, and interface requirements.
2. Call `code_context` with the target variant and public-code scopes.
3. Call `code_impact` for likely entry points.
4. Describe affected modules, state transitions, parameters, input/output signals, fault handling, tests, and regression risks.
5. Label inferred changes separately from source-backed changes.

Read [planning-checklist.md](references/planning-checklist.md) for required plan sections.

## Extend the requirement library

1. Copy the atomic requirement template from the solution package.
2. Split compound prose into independently testable statements.
3. Preserve source document key, version, section, and PDF page.
4. Put normalized machine fields in one `requirement-json` block.
5. Set new mappings to `unknown` or `candidate`; never pre-mark them `matched`.
6. Run the requirements validator before accepting the note.

Read [atomic-schema.md](references/atomic-schema.md) for the schema.

## Evidence rules

- Prefer exact requirement IDs and exact code symbols.
- Restrict variant code to the requested variant; treat other variants as references only.
- Cite repository-relative file paths and line numbers.
- Do not expose confidential source text through a public skill package.
- Do not mark a requirement complete without implementation and verification evidence.

