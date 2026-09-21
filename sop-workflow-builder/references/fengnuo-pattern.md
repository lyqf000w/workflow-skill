# Fengnuo Pattern

The Fengnuo workflow is a staged private-domain conversion workflow. Use it as the source pattern for similar SOP-driven sales, livestream, or customer operation projects.

## Pattern Summary

- Split the business by day: Day1, Day2, Day3, Day4.
- Use `conversation.step` as the current stage.
- Use `sys.query` as the current trigger.
- Use completion flags such as `EP1`, `EP2`, `EP3`.
- Use extractor variables for key user information, such as `isName`, `isPhone`, and `isAdd`.
- Use fixed answer nodes for SOP messages.
- Use LLM nodes for business Q&A, intent judgment, answer checking, and fallback response.
- Add no-reply guards using `__NO_REPLY__`.
- Add hard handoff rules for risky, high-value, payment, complaint, or exception intents.

## Original Day Structure

Day1:
- Add-friend welcome.
- Collect name, phone, and shipping address.
- Remind the customer to watch the first livestream.
- If information is incomplete, keep asking for the missing field.

Day2:
- Send the first episode livestream link.
- Handle mid-stream exit and recall.
- Judge completion state for EP1.
- Judge the answer for the first question.
- Send different 18:00 messages for completed and incomplete users.

Day3:
- Send the second episode livestream link.
- Route by EP1 and EP2 completion states.
- Support replay, makeup watching, and makeup answering.
- Judge the second question.

Day4:
- Send the third episode livestream link.
- Route by EP1, EP2, and EP3 completion states.
- Support replay and makeup watching across previous episodes.
- Judge the third question.
- Allow membership answers only after the right stage and only when the customer asks.

## Reusable Translation

When adapting this pattern to a new business:

- Replace days with business stages.
- Replace episode flags with milestone flags.
- Replace answer checking with qualification, eligibility, or intent checking.
- Replace livestream time triggers with channel, time, behavior, or user-message triggers.
- Replace welfare registration with lead capture, appointment booking, or sales handoff.
- Replace membership rules with pricing, contract, demo, POC, or procurement handoff rules.

## Guardrails

- Build deterministic branches for stage movement.
- Keep fixed SOP messages out of LLM prompts when exact wording matters.
- Use LLM nodes for uncertain language understanding, not for core routing when a variable can decide.
- Add a no-reply guard after each LLM node that can return `__NO_REPLY__`.
- Add explicit human handoff for complaints, payment, commitments, contracts, legal, pricing uncertainty, and procurement requests.
