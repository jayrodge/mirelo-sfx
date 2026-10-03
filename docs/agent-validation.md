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
