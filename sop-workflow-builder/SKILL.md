---
name: sop-workflow-builder
description: Build reusable SOP-style workflow agents for staged business processes such as private-domain sales follow-up, livestream operations, customer service, presales qualification, lead scoring, and multi-step conversion workflows. Use when the user wants to design, analyze, rebuild, or adapt a workflow using state variables, conditional branches, fixed message nodes, LLM nodes, handoff rules, no-reply guards, and test cases.
---

# SOP Workflow Builder

Use this skill to design workflow agents with the user's preferred state-machine method.

## Core Rule

Design the workflow before writing prompts.

Do not start from a single large prompt. First turn the business process into stages, variables, events, branches, fixed replies, LLM responsibilities, and handoff rules.

## Method

1. Identify the business goal and conversion target.
2. Split the lifecycle into stages or separate agents.
3. Define state variables that control routing.
4. Define event triggers that enter the workflow.
5. Build conditional branches before LLM nodes.
6. Use fixed answer nodes for deterministic SOP messages.
7. Use LLM nodes only for open-ended judgment, Q&A, summarization, recommendation, extraction, and scoring.
8. Add human handoff, no-reply guards, and safety boundaries.
9. Produce a node table and test cases.

## Required Output

For each new business, produce these sections:

- Business goal
- Agent split
- State variables
- Event triggers
- Workflow node table
- Fixed answer nodes
- LLM nodes and responsibilities
- Human handoff rules
- No-reply or no-action rules
- Test cases
- Gaps that must be confirmed before production

## Node Table

Use this table format:

| Node | Type | Input | Condition | Action | Output Variable | Next |
|---|---|---|---|---|---|---|

Keep node names concrete enough that the user can directly recreate them in a workflow builder.

## Design Rules

- Use variables such as `stage`, `intent`, `product_interest`, `customer_stage`, `need_human`, and business-specific completion flags.
- Do not let the LLM decide core stage transitions when deterministic state variables are available.
- Keep business-critical promises, pricing, payment, contract, refund, legal, and complaint handling behind fixed rules or human handoff.
- Separate fixed response content from LLM-generated response content.
- Use a no-reply sentinel such as `__NO_REPLY__` only when the latest user message is a pure acknowledgement and contains no new question or business intent.
- Add a guard after any LLM node that can output `__NO_REPLY__`.
- Preserve the distinction between "answer the customer" and "summarize for sales"; use separate nodes for each.

## References

Read `references/fengnuo-pattern.md` when adapting from the Fengnuo livestream workflow pattern.

Read `references/workflow-blueprint-template.md` when producing a new workflow design for a fresh business.

Read `references/shenzhou-digital-pattern.md` when the business is the Shenzhou Digital chatbot project or a B2B presales lead-qualification workflow.
