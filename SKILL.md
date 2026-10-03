---
name: mirelo-sfx
description: "Add synced sound effects to a silent video with Mirelo SFX (a PAID API). The only tool is `python3 ~/mirelo-sfx/mirelo.py`; there is no mirelo-sd, gen, or other command. For an explicit generation or refinement request, run `python3 ~/mirelo-sfx/mirelo.py generate --video <video.mp4> --prompt \"<sound description>\"` immediately; it uploads, quotes, checks affordability and submits one variant. A cost-only request uses preflight and must never generate. Demo clip: ~/mirelo-sfx/examples/alien-shooter.mp4. Report onsets, sync, credits and times exactly as the JSON prints them (never round; estimated_ms is an estimate). No sound description from the user? Ask or state the chosen prompt. Offer nothing beyond this skill. Read this SKILL.md before use."
---

# Mirelo SFX

Adds sound effects to a short silent video with Mirelo SFX 1.6 and builds a
before/after player. The only tool is `python3 ~/mirelo-sfx/mirelo.py`.
Every command prints one JSON object. On failure it prints
`{"error": ..., "message": ...}` and exits non-zero. Report what the JSON says;
never guess output you did not see.

## Rules

- An explicit request to generate sound or refine an existing result authorizes
  one paid generation. Run `generate` immediately; it uploads, quotes,
  checks the available balance, then submits one variant. There is no default
  credit cap; pass `--max-credits` only if the user requested a limit.
  Do not add a separate cost-approval step.
- For a cost-only request, run `preflight` and report `quoted_credits` and
  `estimated_ms`. It uploads and quotes without generating; never follow a
  cost-only request with `generate`.
- A saved quote is bound to its video and sound description. If either changes,
  run a fresh `preflight` with the intended inputs, then continue `generate`
  for an explicit generation request. A promptless quote also needs a fresh
  preflight with the chosen description. Do not pause for cost approval.
  The run keeps a local snapshot of the uploaded video and optional sync sidecar;
  do not edit those saved files.
- Refine only when the user requests it, using a new `--out` folder. Never
  generate extra variants or automatically iterate on a result.
- **Report the JSON exactly.** Copy `sync.detected_onsets_s`, `sync.ok`,
  credits and job ids as printed. Never round them, and never report the
  `expected_impacts_s` times as detected sounds. `estimated_ms` is Mirelo's
  estimate: say "estimated", never "took" or "generated in".
- If the user gave no sound description, ask for one, or say plainly which
  prompt you will use. Do not silently invent one.
- Do only what this skill does. Do not offer to serve, host, share or send
  the results.
- Use only `mirelo.py`. Never call the Mirelo API with curl or Python, and
  never invent subcommands (`gen`, `run`, `mirelo-sd`, etc. do not exist).
- Never read, print, copy, or edit `.env` or `~/.config/mirelo/credentials`,
  and never put an API key in a message or command. On `CredentialError`,
  stop and tell the user to add the key by hand.
- On `InsufficientCredits`, stop and report it. If the user requested a
  limit, pass that limit with `--max-credits` and stop on `CreditCapError`.
  Do not raise a requested limit, trim, or re-encode the video unless the
  user asks. Never add a credit cap the user did not request.
- One `--out` folder per generation. If `generate` returns
  `"status": "poll_timeout"`, run `resume` for that folder. Never run
  `generate` again for it; that could pay twice.
- If `generate` fails with a network or server error before a `job_id` was saved,
  re-run the exact same `generate` command. The saved idempotency key makes
  that safe. Do not run `preflight` or change the prompt for a pending submission.
  Mirelo remembers the key for 24 hours. If the tool refuses recovery because
  that window expired or is unknown, stop and reconcile the original job with
  Mirelo; do not create another run to bypass the guard.

The default example is original alien-shooter arcade gameplay: a player ship
moves and fires, three enemies explode, and the score rises. Kill events occur
at 1.8, 4.0 and 6.2 seconds. Its optional sync sidecar records those expected
events; report measured onsets and sync exactly, without inferring listening
quality. Let an audience member choose a sound description, then request one
generation. Do not generate extra styles automatically. The ball clip remains
the historical sync fixture; Artemis remains an alternative footage example
with source credit in `examples/README.md`.

## Workflow

1. For a generation request, run one command. Its JSON includes the quote,
   charged credits, status and output paths:

   ```bash
   python3 ~/mirelo-sfx/mirelo.py generate \
     --video ~/mirelo-sfx/examples/alien-shooter.mp4 \
     --prompt "Three powerful arcade laser-blast explosions synchronized to the three enemy hits at 1.8, 4.0, and 6.2 seconds. Each burst has a crisp electronic zap and crunchy explosive hit with a short decay. Quiet between bursts. No music, speech, ambience or extra shots."
   ```

2. If the status is `poll_timeout`:

   ```bash
   python3 ~/mirelo-sfx/mirelo.py resume --out <out>
   ```

3. For a requested refinement, run `generate` with the refined prompt and a
   new `--out` folder. Each requested refinement is one paid job.

For a cost-only request, use `preflight` with the video and intended prompt.
Report the quote and stop; the optional paid command in `next` is not
permission to generate.

## What to report

When `status` is `done`: the paths in `files` (`silent`, `sound`,
`with_sound`, `player`), the `job_id`, `quoted_credits` and `charged_credits`,
and `sync`: the `detected_onsets_s` exactly as printed, plus `ok` and
`expected_impacts_s` only when present (label the latter as expected). For any other status, report `status` and
`message` and the next command these rules allow.
