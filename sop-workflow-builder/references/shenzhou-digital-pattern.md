# Shenzhou Digital Pattern

Use this reference for the Shenzhou Digital chatbot project or similar B2B presales workflows.

## Business Translation

The Shenzhou Digital project is not a generic FAQ bot. Treat it as a B2B presales and customer-operation workflow:

- Identify product direction.
- Answer product questions from knowledge.
- Probe customer needs.
- Capture contact and company information.
- Score lead quality.
- Route high-intent leads to sales.
- Summarize the conversation for sales follow-up.

## Recommended Agent Split

Start with one entry agent and product-specific subflows:

- Entry / intent routing agent.
- Shenzhou Wenxue product agent.
- Shenzhou Kuntai product agent.
- Overseas solution agent.
- AI API platform agent.
- Lead qualification and handoff agent.

For a POC, one workflow can contain these as branches. For production, separate high-complexity product lines into dedicated agents or sub-workflows.

## Suggested State Variables

| Variable | Meaning | Example Values |
|---|---|---|
| `channel` | Customer channel | website, wecom |
| `customer_stage` | Current sales stage | new, product_identified, needs_probed, contact_collected, handed_off |
| `product_interest` | Product direction | wenxue, kuntai, overseas, ai_api, unknown |
| `intent` | Latest user intent | faq, pricing, demo, technical, case, procurement, complaint, unclear |
| `company_name` | Customer company | free text |
| `industry` | Customer industry | finance, manufacturing, government, education, unknown |
| `role` | Customer role | business, IT, procurement, executive, unknown |
| `pain_point` | Main need | free text |
| `budget` | Budget signal | known, unknown, refused |
| `timeline` | Purchase or project cycle | immediate, this_quarter, unknown |
| `contact` | Contact info | phone, wechat, email, unknown |
| `lead_score` | Lead level | A, B, C, unknown |
| `need_human` | Whether sales should take over | true, false |
| `handoff_reason` | Reason for handoff | demo, quote, POC, procurement, complaint |

## Entry Branches

Use deterministic branches where possible:

- User asks "你们能做什么" -> product direction clarification.
- User names a product -> product-specific agent.
- User asks price, demo, POC, contract, procurement -> handoff after collecting minimum context.
- User describes a business pain -> need probing then recommendation.
- User leaves contact -> create lead summary and handoff.
- User asks unsupported or risky question -> safe fallback or handoff.

## Product Branch Logic

Shenzhou Wenxue:
- Focus on enterprise knowledge base, Agent Workspace, digital workers, knowledge governance, model scheduling, private deployment, enterprise internal enablement.
- Probe use case, department, system integration, deployment preference, data sensitivity, and user scale.

Shenzhou Kuntai:
- Focus on domestic infrastructure, Xinchuang, servers, computing resources, adaptation, government/enterprise scenarios.
- Probe industry, procurement context, hardware/software stack, timeline, and project type.

Overseas solutions:
- Focus on overseas acceleration, security, CDN, cloud network, customer service, and partners such as Akamai, Zenlayer, Imperva, Zendesk when supported by provided materials.
- Probe target region, business type, traffic/security pain, current provider, and urgency.

AI API platform:
- Focus on AI capability access, model/API service, integration, scenario verification, and enterprise application.
- Probe use case, expected model capability, integration system, data policy, and POC needs.

## Handoff Rules

Set `need_human=true` when:

- The customer asks for quotation, price, contract, procurement, bidding, POC, or demo.
- The customer provides phone, email, WeChat, company name plus clear need.
- The customer asks for capability commitments not explicitly supported by knowledge.
- The customer asks about legal, compliance, security incident, or contract terms.
- The customer has high intent after needs probing.

## Lead Scoring

Score A:
- Clear product interest.
- Clear business pain.
- Company or organization known.
- Contact provided or demo/POC requested.
- Timeline or budget signal exists.

Score B:
- Clear product interest and business pain, but no contact or timeline.

Score C:
- General inquiry, unclear need, student/research, competitor probing, or no business context.

## Required Output Shape

When designing a Shenzhou workflow, include:

- Entry routing table.
- Product-specific branch table.
- Need-probing questions.
- Fixed answer nodes.
- LLM node prompts at responsibility level, not huge final prompts unless asked.
- Sales handoff summary schema.
- Test cases for each product branch and each handoff rule.
