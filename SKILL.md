---
name: mirelo-sfx
description: "Generate sound effects for silent videos, or quote their cost, using Mirelo's paid SFX API."
---

# Mirelo SFX

Use your shell/terminal tool to run the helper below. Read this file with a
file-read tool (OpenClaw) or `skill_view` (Hermes); do not use Skill Workshop
or a code-execution wrapper. The only tool is `python3 ~/mirelo-sfx/mirelo.py`.
It handles uploads, quoting, generation, polling and output assembly, returning
one JSON object. Do not call the API directly or invent subcommands.
Execute this helper for every quote, generation or resume request. For an
existing job, run `resume --out <run-directory>` even if it is already complete;
do not inspect `job.json` to reconstruct its result.

## Report the result

Your final response is the helper's complete JSON unchanged in a fenced `json`
block. Do not add a prose summary or interpret the timing; do not replace values
with a summary table or rounded estimates.
Include every returned field, including `files.job`; do not omit paths.
The returned JSON already includes sync details; no follow-up file read is needed.
`estimated_ms` is an estimate in milliseconds; onset times are seconds.
Expected impacts are not detections.
For the demo, `sync.ok` checks ±0.1 s timing, not the number of extra sounds.
Do not infer quote expiry: the 24-hour rule applies to submission recovery.
For errors or incomplete jobs, report the message and allowed recovery command.
Do not automatically generate extra variants or offer hosting/sharing services.

## Choose the action

- An explicit generation/refinement request authorizes one paid variant.
  Run `generate` directly; it quotes and checks affordability before submission.
  No extra approval or default credit cap. Pass `--max-credits` only for a
  user-requested limit. Refine only when requested, in a new `--out` folder.
- A cost-only request uses `preflight --video <video> --prompt "<description>" --out <run-directory>`.
  Report the quote and stop, even if JSON includes a suggested paid command.
- Use the user's video and sound description. If none was given, ask or state
  the chosen description before generating. The example below is for the demo.

```bash
python3 ~/mirelo-sfx/mirelo.py generate \
  --video ~/mirelo-sfx/examples/alien-shooter.mp4 \
  --prompt "Three powerful arcade laser-blast explosions synchronized to the three enemy hits at 1.8, 4.0, and 6.2 seconds. Each burst has a crisp electronic zap and crunchy explosive hit with a short decay. Quiet between bursts. No music, speech, ambience or extra shots."
```

The demo's expected hits are 1.8, 4.0 and 6.2 seconds. Passing its signal
check permits extra onsets and does not prove listening quality.

## Protect inputs and credits

Resolve a requested output directory and pass it as `--out` in the initial
helper command. The helper creates the directory and saves `job.json` there.
Never write or copy quote JSON yourself, through shell or file tools.

- Never read, print, copy or edit `.env` or `~/.config/mirelo/credentials`;
  the helper reads credentials itself. On `CredentialError`, stop and ask
  the user to configure the key manually. Never put keys in commands or chat.
- Stop on `InsufficientCredits` or a requested limit's `CreditCapError`.
  Do not raise limits, trim or re-encode video without a user request.
- Quotes bind the video and prompt. To change a saved quote, run a fresh
  `preflight` with the intended inputs before `generate`. Never change saved
  video/sidecar snapshots or inputs belonging to a pending submission.
- Use one run folder per generation. On `poll_timeout`, or when a job ID
  already exists, use `resume --out <out>`; never submit another job.
- On a network/server failure before a job ID is saved, retry `generate` with
  unchanged inputs and explicit `--out` pointing to the original folder. Its idempotency key recovers the submission.
  If the helper reports an expired/unknown 24-hour recovery window, stop and
  reconcile the original job with Mirelo; do not bypass it with a new folder.
