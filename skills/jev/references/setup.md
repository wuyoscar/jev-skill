# Set up Jev

This skill is run by the user's own coding agent, not a separate setup app.
Handle environment inspection, installation checks and commands yourself; do not
make the user run a terminal checklist. Ask them to confirm the service/simulation
choice and handle private key entry or approvals. If the host is not identifiable,
ask which coding agent and project to configure before writing files.

Use the user's current host and existing account where possible. Setup is not a
model call, account creation, provider switch or permission to spend.

## Updating an existing installation

When the user asks to update, follow the [agent update guide](https://github.com/wuyoscar/jev-skill/blob/main/docs/update.md).
Update the installed skill files as well as any separate CLI; preserve the chosen
source channel, local edits and provider/simulation mode. Do not run setup again
to silently replace those choices. Verify offline; updating does not authorize API calls.

## Setup: choose the service or simulation

Check only the presence of `OPENROUTER_API_KEY`, `TYPESAFE_API_KEY` and
`BOCHA_JEV_API_KEY`/`BOCHA_SEARCH_API_KEY`; never print credentials. Respect the
user's already chosen mode. For a new setup, prefer the user's existing
OpenRouter account; otherwise offer official TypeSafe or Bocha Jev. If
OpenRouter is missing, explain that direct TypeSafe is also real Jev. Do not
silently change destination, send data, create an account or switch the host model.

If no route has been chosen, explain the available routes and ask:

> **A — Real Jev:** use/get an OpenRouter key at https://openrouter.ai/settings/keys
> if you use OpenRouter; otherwise use/get a TypeSafe key at
> https://console.typesafe.ai. Configure it locally, not in chat.
> **B — Simulate:** use the current agent, or an explicitly selected available
> model such as DeepSeek, with the same context, questions and criteria.

**Wait for an explicit choice.** Do not ask again for every record in the same
approved task. API errors do not authorize switching providers or simulation.
Missing both keys is not a dead end: offer B. It requires no Jev key but the
chosen agent/model's ordinary access, usage costs and privacy terms still apply.
Do not assume DeepSeek is installed, free or locally hosted.

In B, return `mode: agent_simulation` for the current host or
`mode: model_simulation` for another explicitly approved model, plus its actual
model identity when available and `jev_called: false`. Each question has `value`,
`needs_review`, a brief evidence-based `reason`, `probability: null` and
`confidence: null`. Choice values must be supplied labels, Noul values booleans,
and Score values integer rubric indices. Use null/review for missing evidence.
Never present this as Jev, calibrated probability or equivalent speed/accuracy.
Skip Jev CLI/API steps in B; use the approved model's existing interface and do
not install a substitute or send data elsewhere without consent.

In A, select the CLI destination explicitly: `--provider openrouter`,
`--provider typesafe` or `--provider bocha`. The TypeSafe route uses
`TYPESAFE_API_KEY` and maps the bundled OpenRouter model ID to `jev-1.13.0`. The
Bocha route uses `BOCHA_JEV_API_KEY`, with `BOCHA_SEARCH_API_KEY` as fallback,
and maps the bundled IDs to `bocha-jev-v1`. `--dry-run` only validates; it neither
classifies nor makes a network call. `jev-decide setup` reports presence only,
not key validity, credits or permission. Continue below for the selected route, or use the
[copyable simulation prompt](simulation.md).

## Complete the selected route

| Route | Local environment | CLI option | Endpoint / model |
|---|---|---|---|
| OpenRouter | `OPENROUTER_API_KEY` | `--provider openrouter` | `https://openrouter.ai/api/alpha/decisions` / `typesafe/jev-1.13` |
| Official TypeSafe | `TYPESAFE_API_KEY` | `--provider typesafe` | `https://api.typesafe.ai/v1/systemone` / `jev-1.13.0` |
| Bocha Jev | `BOCHA_JEV_API_KEY` (or `BOCHA_SEARCH_API_KEY`) | `--provider bocha` | `https://jev.bocha.cn/v1/systemone` / `bocha-jev-v1` |
| Current agent / approved DeepSeek | Existing host or selected model access | No Jev CLI call | [Simulation prompt](simulation.md); never invent an API receipt |

If the user uses OpenRouter but has no key, point them to its key page. If they
do not use OpenRouter, offer the official console rather than requiring another
aggregator account. If neither route is possible or desired, offer simulation.
A missing key is never a reason to collect a secret in chat or browser history.
Let the user complete account/terms/payment steps; describe environment-variable
names and ask them to configure their host locally. Do not edit shell profiles.

<a id="local-key-setup"></a>
## Agent-side key setup

The native TypeSafe route is already supported; it does not need an OpenRouter
key or a Vercel account. Use **one** matching key/provider pair in the environment
that launches the agent. The lines below contain placeholders, not real secrets;
guide the user to enter their key through the host's local secret/environment settings. Avoid
saving real keys in shell history, chat or tracked files.

```bash
# Official TypeSafe: obtain the key at https://console.typesafe.ai
export TYPESAFE_API_KEY="<your-TypeSafe-key>"
jev-decide setup
jev-decide decide /path/to/request.json --provider typesafe --dry-run
# Only after approval for this input and paid call:
jev-decide decide /path/to/request.json --provider typesafe > result.json
```

```bash
# Alternative: OpenRouter key from https://openrouter.ai/settings/keys
export OPENROUTER_API_KEY="<your-OpenRouter-key>"
jev-decide decide /path/to/request.json --provider openrouter --dry-run
```

```bash
# Alternative: Bocha Jev client key from https://jev.bocha.cn
# A BOCHA_SEARCH_API_KEY that already grants access may be reused.
export BOCHA_JEV_API_KEY="<your-Bocha-Jev-key>"
jev-decide decide /path/to/request.json --provider bocha --dry-run
```

Setting `TYPESAFE_API_KEY` does not select the provider: keep `--provider typesafe`
on native calls even when both keys exist. This CLI does **not** auto-load `.env`.
An already running desktop agent may need a restart to inherit its environment.
Do not print variables to troubleshoot; check presence only. A present placeholder
is still not a valid key. Neither `setup` nor `--dry-run` authenticates it.

Run `jev-decide setup` if already installed. Otherwise check environment presence
with the host tools; the skill does not require Python just to offer choices.
For A, ensure Python 3.10+ and the reviewed shared CLI are available. Use the
selected route above. A dry run maps the known bundled model ID for direct
TypeSafe; use `--model` for a deliberate override.
Report which mode/provider was selected, which prerequisite is missing, what was
actually verified, and the next user action. Do not call an API merely to test a
key. A 401/402/403 is not permission to retry or silently switch services.

The agent does not inherit context into Jev calls. For later work, supply
sufficient context and batch independent questions in the same request; the
host schedules bounded concurrency, not dependent steps in parallel.

[TypeSafe contract](https://docs.typesafe.ai/api) · [TypeSafe models](https://docs.typesafe.ai/models) ·
[OpenRouter contract](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request) ·
[Bocha Jev skill](https://jev.bocha.cn/install/skill.md).
