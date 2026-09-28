# Manual installation and host compatibility

**Already installed?** Give your agent the [update prompt](update.md) to refresh
skills and the existing CLI without changing your setup choices.

**Prefer to let your agent install it?** Copy the prompt from the
[agent installation guide](install.md). The direct-copy route needs no Node/npm.
The commands below are optional manual alternatives, not steps every user must run.

## No key: ask first, then choose a mode

Use [jev setup](../skills/jev/references/setup.md) to check key presence without printing
values. Prefer an existing OpenRouter account; otherwise offer official TypeSafe.
If no route is configured, explain the choices and **wait**:

- **A — Real Jev:** [OpenRouter key](https://openrouter.ai/settings/keys) if you
  use OpenRouter, otherwise [TypeSafe key](https://console.typesafe.ai).
- **B — Simulation:** the current agent or an explicitly approved available model
  such as DeepSeek uses the same evidence, questions and criteria. Install the
  skill folders; no Jev CLI or Jev key is needed. See the
  [copyable simulation prompt](../skills/jev/references/simulation.md).

B outputs are marked `mode: agent_simulation` (host) or `mode: model_simulation` (another approved model), `jev_called: false` and carry no
Jev probabilities (`probability` and `confidence` are `null`). They are not API
results or calibration evidence. The host agent's usual costs/privacy terms still
apply. Never switch to B silently, including after API errors.

The runtime and credentials instructions below apply to **API mode**, not B.

## Pick the surface you need

- **One focused skill:** install the shared CLI, then a scenario skill. The five focused
  skills need no sibling skill and do not duplicate the runtime.
- **General toolbox:** install `jev`. It includes its own stdlib script and the
  full reference library; a separate CLI installation is optional.
- **Manual use:** install only the CLI and edit request JSON yourself.
- **MCP/browser/desktop integrations:** choose a separately maintained upstream
  project from the [ecosystem guide](../skills/jev/references/ecosystem.md).
  Installing our skills does not install those projects or their tools.

## Published release versus reviewed source

The five-entry collection is an unreleased source preview. Published **v0.2.0**
still contains eleven skills; [its pinned guide](install-v0.2.0.md) remains available.
Use the five-entry names below only from an explicitly reviewed five-entry checkout.
For an existing installation, follow [the migration guide](skill-migration.md).

## Optional package-tool and skills-installer route

```bash
uv tool install git+https://github.com/wuyoscar/jev-skill.git@v0.2.0
npx skills add /absolute/path/to/reviewed/source --skill jev-triage
export OPENROUTER_API_KEY="your-key"
```

Select Codex, Claude Code or OpenCode in the installer; replace the skill name
with any entry below. The CLI command above installs the published runtime. The skill command uses an
explicitly reviewed local source. Do not substitute the default branch silently.
For the stable eleven-skill installation, follow the pinned release guide instead.

[Release downloads](https://github.com/wuyoscar/jev-skill/releases/tag/v0.2.0)
include the CLI wheel, source distribution and complete source ZIP. No PyPI
account is needed. Use the key for your selected provider.

## From a reviewed checkout

Select the source commit with the user, inspect it, and record `git rev-parse HEAD`.
Confirm it contains exactly the five entry points below. This is not permission to
replace a published version pin with an arbitrary branch.

In the root of that checkout:

```bash
uv tool install .
npx skills add . --list
npx skills add . --skill jev-triage
```

Python 3.10+ is required. This route also needs uv and Node/npm for the installer;
`pipx install .` is an alternative to `uv tool install .`. Select Codex, Claude Code
or OpenCode in the skills installer. Install only the entries you need:

| Skill | Use it for | Jev API runtime |
|---|---|---|
| `jev` | Setup, custom decisions, routing and context checkpoints | Bundled Python script; CLI optional |
| `jev-triage` | Bulk classification and prioritization | Shared `jev-decide` CLI |
| `jev-documents` | Document evidence and code-location selection | Shared CLI + host reading tools |
| `jev-eval` | Output/code review and authorized safety evaluation | Shared CLI; offline transcript request builder |
| `jev-act` | Browser/desktop steps and legal actions in games or simulations; shared CLI + host tools |

To install from a different project directory, replace `.` in the installer
command with the absolute path to this checkout. Review downloaded instructions
and code before use. No helper needs to change the host's primary model.

## Manual skill installation

Copy the **whole** chosen `skills/<name>` folder, including its assets and any
scripts/references. Do not overwrite an existing skill without review.
Project-local destinations:

| Host | Destination |
|---|---|
| Codex | `.agents/skills/<name>/` |
| Claude Code | `.claude/skills/<name>/` |
| OpenCode | `.opencode/skills/<name>/` (also supports shared `.agents/skills/`) |

See the [Codex docs](https://developers.openai.com/codex/skills/),
[Claude Code docs](https://code.claude.com/docs/en/skills),
[OpenCode docs](https://opencode.ai/docs/skills/) and
[installer documentation](https://github.com/vercel-labs/skills).
Discovery through the installer does not prove native invocation in every host.
Restart/reload as needed and explicitly ask the agent to use the selected skill.
The reference format follows the [Agent Skills specification](https://agentskills.io/specification).

## Credentials and first run

For **A / Jev API mode** only; B skips these calls and uses the selected existing model interface.

Export `OPENROUTER_API_KEY` or `TYPESAFE_API_KEY` for the selected provider in the
environment that **launches the host**. Desktop
apps may not inherit a terminal export. Use the host's documented environment
setup; never put keys in `SKILL.md`, chat, request JSON or version control.

```bash
export OPENROUTER_API_KEY="your-key"
# From the checkout; validation needs no key or network:
jev-decide decide skills/jev-triage/assets/example.json --dry-run
# After editing the synthetic example and reviewing the data to be sent:
jev-decide decide /path/to/edited-request.json
```

### Official native key (no OpenRouter account required)

Obtain a key at the [TypeSafe console](https://console.typesafe.ai) and set it
locally in the host's launch environment. The placeholder below is not a valid
credential. Keep real values out of chat, version control and shell history.

```bash
export TYPESAFE_API_KEY="<your-TypeSafe-key>"
jev-decide setup
jev-decide decide skills/jev-triage/assets/example.json --provider typesafe --dry-run
# Only after approving the data and paid call:
jev-decide decide /path/to/edited-request.json --provider typesafe > result.json
```

The CLI still defaults to OpenRouter, even when only the native key is present;
select `--provider typesafe` explicitly. Neither key works at the other endpoint.
There is no automatic `.env` loading. Configure the actual host process and
restart it when needed; `setup` checks presence, not authentication or credits.
[Setup mode](../skills/jev/references/setup.md#local-key-setup) ·
[Common pitfalls](../skills/jev/references/pitfalls.md#native-key).

### Bocha Jev key

Obtain a client key at [jev.bocha.cn](https://jev.bocha.cn) and set
`BOCHA_JEV_API_KEY` locally in the host's launch environment; an existing
`BOCHA_SEARCH_API_KEY` that already grants access may be reused. Then select
`--provider bocha`, which maps the bundled model IDs to `bocha-jev-v1`.

```bash
export BOCHA_JEV_API_KEY="<your-Bocha-Jev-key>"
jev-decide setup
jev-decide decide skills/jev-triage/assets/example.json --provider bocha --dry-run
# Only after approving the data and paid call:
jev-decide decide /path/to/edited-request.json --provider bocha > result.json
```

The general `jev` skill also works without installing the CLI:

```bash
python3 /actual/skill/path/scripts/jev.py decide request.json --dry-run
python3 /actual/skill/path/scripts/jev.py decide request.json
```

Resolve installed paths relative to the loaded skill, not the host project.
Normal decisions send supplied state/questions to the selected provider and incur usage;
dry runs do neither. Logs may contain supplied text: keep private data out of
public benchmark artifacts. Use `--provider openrouter` (default),
`--provider typesafe` or `--provider bocha` explicitly; the CLI never switches
providers after an error. The official route uses
`https://api.typesafe.ai/v1/systemone` and `TYPESAFE_API_KEY`; the Bocha route
uses `https://jev.bocha.cn/v1/systemone` with `BOCHA_JEV_API_KEY`, or
`BOCHA_SEARCH_API_KEY` when it already grants access.
`jev-decide setup` only reports presence and choices; it does not test credentials.

Default OpenRouter model: `typesafe/jev-1.13`; official: `jev-1.13.0`; Bocha: `bocha-jev-v1`.
Explicit TypeSafe or Bocha selection maps the bundled OpenRouter and TypeSafe IDs
to that route's model.
The OpenRouter API is alpha; test upgrades deliberately.
`--model` overrides request `model`, then `JEV_MODEL`, then the default.

## CLI behavior

The **skill**, not the CLI, handles the A/B conversation. The CLI has no simulation
flag: without a key, a live request returns an error instead of invented decisions.
`--dry-run` still works without a key and validates input only.

CLI installation adds the command, not a host skill. `decide FILE` accepts native
request JSON; use `-` for stdin. `classify` accepts `--text` or `--text-file` and a
JSON `--criteria` file mapping labels to descriptions. Use files/stdin instead
of interpolating untrusted text into shell commands. `jev-decide --help` lists options.

Thresholds default to `--min-probability 0.8` and `--min-margin 0.15`: uncalibrated
starting points, not deployment recommendations. Reserved labels `other`, `unknown`,
`abstain`, `review`, `ask_user`, `wait`, `none`, `defer` and `insufficient_evidence`
produce review status; add task-specific fallback labels with `--review-label`.
Scores are returned, not converted into approvals. HTTP failures are not retried
automatically. Exit codes: **0** selected/scored, **2** review, **1** error.
None grants permission to execute an action.

## Validate or build locally

```bash
python3 -m unittest discover -s tests -v
uv build
```

The wheel installs the shared CLI. The source distribution includes all five
skill folders, docs and evaluation materials. A skill folder copied on its own
needs its documented runtime **for API calls**: bundled Python for `jev`, shared
CLI for the focused skills. Agent simulation needs neither. [Validation scope](validation.md).
