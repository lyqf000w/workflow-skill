# Workflow Blueprint Template

Use this template when designing a new workflow from business materials.

## 1. Business Goal

State what the workflow should accomplish in one sentence.

Examples:
- Convert livestream viewers into qualified private-domain customers.
- Turn website visitors into qualified B2B sales leads.
- Answer product questions and route high-intent customers to sales.

## 2. Agent Split

List whether to build one workflow or multiple agents.

Recommended split patterns:
- By day or campaign stage.
- By product line.
- By customer channel.
- By risk level or human handoff.

## 3. State Variables

Define variables before node design.

Use this format:

| Variable | Type | Meaning | Example Values | Owner |
|---|---|---|---|---|

Typical variables:
- `stage`
- `intent`
- `customer_stage`
- `product_interest`
- `need_human`
- `handoff_reason`
- `lead_score`
- milestone flags such as `EP1`, `EP2`, `demo_requested`, `contact_collected`

## 4. Event Triggers

List all workflow entry events.

Use this format:

| Trigger | Source | Meaning | Initial Branch |
|---|---|---|---|

Typical triggers:
- new user enters
- user message
- timer
- behavior event
- form submitted
- link clicked
- content watched
- contact provided

## 5. Workflow Node Table

Use this format:

| Node | Type | Input | Condition | Action | Output Variable | Next |
|---|---|---|---|---|---|---|

Node type examples:
- start
- if-else
- assigner
- parameter-extractor
- answer
- llm
- knowledge-retrieval
- tool
- message-notice
- jump-agent
- human-handoff

## 6. Fixed Answer Nodes

List fixed messages that must not drift.

Common fixed messages:
- welcome
- choose product direction
- ask for missing information
- collect contact
- transfer to sales
- cannot answer safely
- pricing or contract handoff

## 7. LLM Nodes

For each LLM node, specify:

| LLM Node | Responsibility | Inputs | Must Output | Must Not Do |
|---|---|---|---|---|

Good LLM responsibilities:
- classify intent
- answer product FAQ from knowledge
- extract structured needs
- recommend product direction
- summarize for sales
- score lead quality

Avoid:
- making binding price promises
- inventing product capabilities
- bypassing stage variables
- deciding payments, contracts, or refunds

## 8. Handoff Rules

Define hard rules that force `need_human=true`.

Common handoff triggers:
- asks for quotation
- asks for contract
- asks for procurement or bidding
- asks for POC or demo
- provides contact information
- complains or escalates
- asks for legally or commercially sensitive commitments
- asks beyond the knowledge base after one clarification

## 9. No-Reply Rules

Define when the bot should not reply.

Safe no-reply cases:
- Pure acknowledgements: "好的", "收到", "嗯", "OK".
- No question, no business keyword, no new intent.

Unsafe no-reply cases:
- Any question mark.
- Mentions price, product, demo, contact, contract, delivery, refund, complaint, or business problem.
- User provides new information.

## 10. Test Cases

Create tests before considering the workflow complete.

Use this format:

| Case | Input State | User/Event | Expected Node | Expected Reply/Variable |
|---|---|---|---|---|

Include:
- happy path
- missing information
- wrong stage
- high-intent handoff
- FAQ
- no-reply
- out-of-scope
- contradiction or unclear intent
