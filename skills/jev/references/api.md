# Jev through OpenRouter, official TypeSafe or Bocha Jev

Provider contracts checked against public documentation on **2026-09-21**; direct TypeSafe transport is mock-tested, not live-tested here. The Decisions endpoint is **alpha**; pin a model and recheck this contract before upgrading.

## Transport

```text
POST https://openrouter.ai/api/alpha/decisions
Authorization: Bearer $OPENROUTER_API_KEY
Content-Type: application/json
```

This is **not** `/api/v1/chat/completions`, `/api/v1/decisions`, or TypeSafe's direct `/v1/systemone` endpoint. Send `state` and `questions`, not `messages`. No second TypeSafe key is needed. [OpenRouter Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request)

For the OpenRouter TypeScript SDK, use a separate Decisions client with `serverURL: 'https://openrouter.ai'`; the cookbook documents a 404 with the default base URL in SDK 1.2.146. [Verified-cascade cookbook](https://openrouter.ai/docs/cookbook/evaluate-and-optimize/jev-verified-cascade)

## Official TypeSafe route

Select it deliberately with `--provider typesafe`; use `TYPESAFE_API_KEY`.
The endpoint is `POST https://api.typesafe.ai/v1/systemone`, with Bearer auth and
the same state/questions shape. Its pinned model is `jev-1.13.0`. Only the known
bundled `typesafe/jev-1.13` ID is mapped when selecting TypeSafe; an explicit
`--model` override is not rewritten. Response validation and review policy are
shared. Keys are bound to fixed provider endpoints; no arbitrary base URL,
automatic service switching, retry or simulation is provided.

`jev-decide setup` checks presence only and explains A/B choices. See the
[setup skill](https://github.com/wuyoscar/jev-skill/blob/main/skills/jev/references/setup.md)
and [official API](https://docs.typesafe.ai/api), [model IDs](https://docs.typesafe.ai/models).

## Bocha Jev route

Select it deliberately with `--provider bocha`; use `BOCHA_JEV_API_KEY`, falling
back to `BOCHA_SEARCH_API_KEY` when that key already grants access. The endpoint
is `POST https://jev.bocha.cn/v1/systemone`, with Bearer auth and the same
state/questions shape. Its model is `bocha-jev-v1` (`bocha-jev-latest` and
`jev-latest` are aliases). Selecting Bocha maps the bundled `typesafe/jev-1.13`
and `jev-1.13.0` IDs to `bocha-jev-v1`; an explicit `--model` override is not
rewritten. Successful replies carry top-level `model`, `answers`, `usage` and
`metadata`; Noul returns a probability of true, Score a zero-based weighted
index with a `legend`, and Choice a highest-probability candidate. Request and
question validation, response validation and review policy are shared. Each
complete question, including all its candidates, is limited to 32768 tokens.
Keys are bound to fixed provider endpoints; no arbitrary base URL, automatic
service switching, retry or simulation is provided.

## Native request

The following is an authored example, not a captured model result:

```json
{
  "model": "typesafe/jev-1.13",
  "state": {
    "goal": "Fix the parser and verify the original tests.",
    "observations": ["The original regression still fails."],
    "proposed_action": "Remove the failing assertion."
  },
  "questions": {
    "next_step": {
      "type": "choice",
      "instructions": "Which supplied next step fits the observed task state?",
      "criteria": {
        "inspect_failure": "The original regression remains unresolved; investigate it.",
        "verify_completion": "Implementation work is finished; rerun the original checks.",
        "defer": "The available evidence does not justify either supplied step."
      }
    },
    "weakens_check": {
      "type": "noul",
      "instructions": "Would proposed_action remove or weaken an existing correctness check?",
      "criteria": {
        "true": "An existing assertion or test would become less capable of detecting failure.",
        "false": "Existing checks remain intact or become stronger."
      }
    },
    "evidence_strength": {
      "type": "score",
      "instructions": "How strongly do observations support completion of goal?",
      "criteria": [
        "The observations include an unresolved failure of an original requirement.",
        "Some original requirements have passed checks, but others lack results.",
        "All original requirements have direct passing verification results."
      ]
    }
  }
}
```

Save a native request as `request.json`, then call it without putting a key in the file:

```bash
curl --fail-with-body https://openrouter.ai/api/alpha/decisions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H 'Content-Type: application/json' \
  --data-binary @request.json
```

`state` accepts a string, JSON object, or array. All questions see that same state and are evaluated independently. Use named fields and supply the evidence needed for the decision; do not assume a question can read another question's answer. Jev is text-only, so browser DOM text or an accessibility snapshot is suitable; screenshots require a separate perception step. [State](https://docs.typesafe.ai/concepts/state)

## Questions and answers

| Primitive | Request `criteria` | Response fields | Meaning |
| --- | --- | --- | --- |
| `choice` | Required object: option name → description | `type`, `choice`, `probabilities`, `confidence` | One supplied option wins; probabilities cover all options. |
| `noul` | Optional object with both `true` and `false` descriptions | `type`, `noul` | Probability of yes, from 0 to 1. **No separate confidence field.** |
| `score` | Required ordered array of 2–10 descriptions | `type`, `score`, `legend`, `probabilities`, `confidence` | Probability-weighted level index; fractional values are normal. |

`instructions` is required. Instructions and descriptions may be strings, JSON objects, or arrays; Choice descriptions may also be `null`. Prefer descriptive strings for small requests. Choice supports up to 255 options. Score indices start at zero, so three levels produce values between 0 and 2, not 0 and 1. Probability and legend keys for Score are strings such as `"0"`. [Choice](https://docs.typesafe.ai/primitives/choice), [Noul](https://docs.typesafe.ai/primitives/noul), [Score](https://docs.typesafe.ai/primitives/score), [HTTP schema](https://docs.typesafe.ai/api)

The response envelope contains `model`, `answers`, and `usage`; OpenRouter also documents `id` and `provider`. `answers` uses the original question IDs. Usage includes `input_tokens`, `output_tokens`, and, when available, `cost` in USD. Preserve returned metadata rather than estimating spend from advertised latency or assuming the requested alias equals the resolved model. [OpenRouter Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request)

## Confidence is not probability

- `probabilities[answer.choice]` is the selected option's probability.
- `confidence` summarizes the shape of the whole Choice/Score distribution. It is **not** an alias for the largest probability, and it is not proof that the answer is correct.
- `noul` is already the yes-probability; do not fabricate a `confidence` field for it.
- A score measures a rubric position, not certainty. Inspect its distribution and confidence separately.

Thresholds require calibration on the actual task, model version, and question. Closely related valid actions can split Choice probability, so a low-confidence browser choice need not mean every action is bad. [Confidence](https://docs.typesafe.ai/confidence)

## Current model and budgets

OpenRouter lists `typesafe/jev-1.13`, released September 18, 2026, at **$0.042 per million input tokens**, with free output tokens and a **32,000-token** context listing. Prices and availability can change. [Model card](https://openrouter.ai/typesafe/jev-1.13)

TypeSafe's direct model ID is `jev-1.13.0`, not the OpenRouter ID. Its documentation distinguishes **64k total tokens** across state and all questions from **32k for state plus the longest question**. Those are upstream limits, not a promise that every OpenRouter request up to 64k is accepted. Keep OpenRouter requests conservative and test the actual route. English is the best-supported language; evaluate CJK workloads separately. [Models](https://docs.typesafe.ai/models)

## Errors, privacy, and execution

- Validate the response before using it: required question IDs, matching answer types, finite probabilities in `[0, 1]`, and known Choice labels. Missing or malformed answers are errors, never approval.
- This wrapper tolerates probability rounding but caps total mass error at 0.05. A high-cardinality distribution with more rounding loss is rejected rather than silently normalized; shortlist or split candidates before trying again.
- OpenRouter documents request/authentication/credit/size/rate/provider failures, including HTTP 400, 401, 402, 403, 404, 413, 429, and 5xx. This CLI never retries automatically. If a caller deliberately implements retries, bound them and include their cost; do not retry invalid credentials or insufficient credits indefinitely.
- A result is a judgment, not execution or permission. Keep command allowlists, user approvals, side-effect limits, idempotency, and postcondition checks outside Jev. An unavailable classifier must not silently approve an action. [Tool-gating cookbook](https://openrouter.ai/docs/cookbook/building-agents/gate-tool-calls-with-jev)
- Send only necessary, authorized context. Never send API keys, session cookies, or unrelated private files. Treat any saved request/response trace as potentially sensitive. TypeSafe states it does not train on customer data; its documented enterprise ZDR offering does **not** establish universal zero retention for an OpenRouter route. [TypeSafe legal](https://docs.typesafe.ai/legal)

For question design, failure modes, and safe abstention, read [question-design.md](question-design.md).
