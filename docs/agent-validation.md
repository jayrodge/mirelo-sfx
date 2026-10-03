# OpenClaw and Hermes skill validation

Both agents loaded the installed `mirelo-sfx` skill, performed a cost-only
quote without submitting a job, then generated one requested arcade sound
design. These checks used the original eight-second alien-shooter clip on
dspark. The screenshots capture real sessions; they are not mockups.

## Execution environments

| Agent | Version | Execution |
| --- | --- | --- |
| OpenClaw | `2026.9.4` | Clean temporary package and isolated state, embedded default `main` agent; same-state temporary gateway for the screenshot |
| Hermes | `v0.21.1 (2026.9.7)` | Native installation, local terminal tool; dashboard resumed the CLI session |

Agent reasoning used the local model `nvidia/Qwen3.6-35B-A3B-NVFP4`.
Mirelo generated sound through its hosted API. Hermes selected Qwen with a
per-invocation override: its existing config's stale Qwopus model setting
was preserved rather than rewritten.

The OpenClaw check preserved the native `2026.9.7` gateway and its schema-19
database. The screenshot uses a temporary `2026.9.4` gateway reading the same isolated
state as the embedded run; it uses no native-gateway session import. The
isolated `2026.9.4` agent run demonstrates that version's skill execution; it does not establish a native `2026.9.4` gateway restoration or
compatibility with the existing schema-19 database.

## Cost-only requests

For both agents, `preflight` returned:

- Quoted credits: `80`.
- Estimated generation time: `16411` ms (an estimate, not measured elapsed time).
- Job ID: `null`.
- No generation submitted and no generation charge.

## Requested generation

| Agent | Job ID | Quoted / charged credits | Status | Detected onsets, seconds | `sync.ok` |
| --- | --- | --- | --- | --- | --- |
| Hermes | `6c4ba76e1d683cac26920caf01f8deeb` | `80 / 80` | `done` | `[0.0, 1.82, 4.08, 6.26]` | `true` |
| OpenClaw | `e108de5f2467e9b8e08eaaadd0604711` | `80 / 80` | `done` | `[0.02, 0.42, 1.82, 4.02, 6.26]` | `true` |

Expected hit times are `[1.8, 4.0, 6.2]` seconds. The detector checks for
an onset within ±100 ms of each expected event; it permits extra onsets.
Both runs have extra detected sounds, so a passing check does not mean
perfect silence between hits or perceptual sound quality.

The Hermes run completed before removal of the default cap, with an explicit
80-credit limit. The later OpenClaw run used the updated skill with no
default credit cap. Current `generate` quotes, checks affordability and
submits one variant. An optional `--max-credits` limit applies only when
requested; cost-only requests still stop after `preflight`.

## Screenshots and interpretation

![OpenClaw session](screenshots/openclaw.png)

The OpenClaw agent's displayed phrase “ms as printed” is incorrect: detected
onsets above are **seconds**. The screenshot is preserved unchanged; the
JSON values and units in this record are authoritative.

![Hermes session](screenshots/hermes.png)

Hermes interpreted the `0.0` onset as the track start. That interpretation
was not independently established: the detector reported an onset at `0.0`
seconds, and the record makes no further claim about its cause.

## Automated checks and remaining validation

The local suite passed **61 tests** on Python **3.12 and 3.14**. Tests mock
Mirelo API calls and exercise local media processing without spending credits.
The suite covers installation for both agents, direct generation, cost-only
requests, affordability, optional limits, input mismatch and recovery.

CI must pass for the published commit before describing that commit as CI
verified. These agent checks do not establish readiness on a freshly imaged
event machine, reboot persistence, or speaker audibility in a crowded room.

## Exact shortened README prompt, October 3, 2026

Tested the Try-it prompt verbatim from commit `7f2d620`, after cloning the
private repository to `~/mirelo-sfx` and installing the skill for both agents.
The checks used the same runtime arrangements described above. Both agents
expanded the short request to the detailed example sound description in
`SKILL.md` and completed one generation, quoted/charged at 80 credits each.

| Agent | Job ID | Detected onsets, seconds | `sync.ok` |
| --- | --- | --- | --- |
| OpenClaw | `d62f55631701f14109e6b3fd53fe660f` | `[0.56, 1.9, 4.06, 6.34]` | `false` |
| Hermes | `2b53fb87262b916a49e763b307033e15` | `[1.74, 4.1, 5.2, 6.28]` | `true` |

The prompt works through both agent workflows. Sound timing varies: the
OpenClaw result's last onset was 140 ms late, outside the detector's
100 ms tolerance. Extra onsets are present in both results. No additional
generation or automatic refinement was run. Inspect playback and use the
bundled successful sample for a predictable presentation fallback.

[Exact request and saved result metadata](readme-prompt-validation.json).

## Compact skill follow-up, October 3, 2026

Live checks exposed output-directory mistakes, rounded estimates and omitted
result paths. The revised skill keeps its 15-word discovery description and
restores focused instructions for direct `--out`, complete JSON reporting and
helper-based resume. The body is 619 words including frontmatter, versus 900
before compaction. The Python helper and API generation parameters are unchanged.

Both agents preserved the exact requested prompt and source-video hash, saved
to the requested run directory, and completed one generation without another
approval. Cost-only requests left job IDs and charges null. The two generations
spent 160 credits total (3908 to 3748); subsequent resumes spent nothing.

| Agent | Job ID | Quoted / charged | Detected onsets (s) | `sync.ok` |
| --- | --- | --- | --- | --- |
| OpenClaw | `f4462b771d9272187328ae7cf2101084` | 80 / 80 | `[1.8, 4.04, 6.26]` | true |
| Hermes | `2078ce815337fa7dbc18cc626b245913` | 80 / 80 | `[0.32, 1.96, 2.8, 4.18, 5.08, 6.34]` | false |

The final free resume checks returned JSON matching the helper for both agents,
including every output path. The explicit tested resume request was:

> Read the installed mirelo-sfx skill and use its resume command for the existing job in ~/mirelo-sfx/runs/RUN-DIRECTORY. Return the helper JSON without generating another variant.

The final Hermes cost-only response preserved all quoted values but omitted the
optional `max_credits: null` field and added prose despite the JSON-only rule.
Earlier generic resume requests bypassed the helper, and some sessions attempted
blocked code wrappers or Skill Workshop before recovering to the correct tool.
These are remaining agent instruction-following limitations; complete verbatim
reporting is not guaranteed on every turn. Use helper JSON and saved artifacts
as authoritative evidence. Both agents reported the actual sync boolean.

The Hermes audio missed all three ±100 ms timing windows despite exact input
forwarding. This check establishes correct skill execution, not reproducible
Mirelo audio quality or crowd-floor audibility. No automatic refinement ran.

[Structured requests, tool commands and result comparisons](compact-skill-validation.json).
