---
name: mirelo-sfx
description: "Add synced sound effects to a silent video with Mirelo SFX (a PAID API). The only tool is `python3 ~/mirelo-sfx-openclaw/mirelo.py`; there is no mirelo-sd, gen, or other command. ALWAYS run the free quote first: `python3 ~/mirelo-sfx-openclaw/mirelo.py preflight --video <video.mp4> --prompt \"<sound description>\"`. Tell the user the quoted_credits and ASK before running the paid `python3 ~/mirelo-sfx-openclaw/mirelo.py generate --video <same video> --prompt \"<same prompt>\" --out <out from preflight>`. Demo clip: ~/mirelo-sfx-openclaw/examples/silent.mp4. Report onsets, sync, credits and times exactly as the JSON prints them (never round; estimated_ms is an estimate). No sound description from the user? Ask. Offer nothing beyond this skill. Read this SKILL.md before use."
---

# Mirelo SFX

Adds sound effects to a short silent video with Mirelo SFX 1.6 and builds a
before/after player. The only tool is `python3 ~/mirelo-sfx-openclaw/mirelo.py`.
Every command prints one JSON object. On failure it prints
`{"error": ..., "message": ...}` and exits non-zero. Report what the JSON says;
never guess output you did not see.

## Rules

- **Preflight first, every time.** `preflight` is free: it uploads the video
  and returns `quoted_credits`. `generate` spends credits. Never run `generate`
  until you have shown the user the quote and they said yes.
- Quote the exact video and sound description you intend to generate. If either
  changes, run a fresh `preflight` and ask for approval of that quote. A quote
  without `--prompt` also needs a fresh preflight with the chosen description.
  The run keeps a local snapshot of the uploaded video and optional sync sidecar;
  do not edit those saved files.
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
- Each job is capped at 80 credits. On `CreditCapError` or
  `InsufficientCredits`, stop and report it. Do not raise `--max-credits`,
  trim, or re-encode the video unless the user asks.
- One `--out` folder per generation. If `generate` returns
  `"status": "poll_timeout"`, run `resume` for that folder. Never run
  `generate` again for it; that could pay twice.
- If `generate` fails with a network or server error before a `job_id` was saved,
  re-run the exact same `generate` command. The saved idempotency key makes
  that safe. Do not run `preflight` or change the prompt for a pending submission.
  Mirelo remembers the key for 24 hours. If the tool refuses recovery because
  that window expired or is unknown, stop and reconcile the original job with
  Mirelo; do not create another run to bypass the guard.

## Workflow

1. Quote (free). The JSON includes `quoted_credits`, `out`, and a ready-made
   `next` command:

   ```bash
   python3 ~/mirelo-sfx-openclaw/mirelo.py preflight \
     --video ~/mirelo-sfx-openclaw/examples/silent.mp4 \
     --prompt "Two soft rubber-ball impacts matching the bounces, quiet room ambience"
   ```

2. Tell the user: "This will cost N credits (cap 80), estimated time about
   X s. Go ahead?" Stop and wait.

3. Only after a yes, run the paid step with the same video and prompt and the
   `out` from step 1:

   ```bash
   python3 ~/mirelo-sfx-openclaw/mirelo.py generate \
     --video ~/mirelo-sfx-openclaw/examples/silent.mp4 \
     --prompt "<same prompt>" --out <out from step 1>
   ```

4. If the status is `poll_timeout`:

   ```bash
   python3 ~/mirelo-sfx-openclaw/mirelo.py resume --out <out>
   ```

5. For a refinement, run steps 1-3 again with the refined prompt (a new `out`).

## What to report

When `status` is `done`: the paths in `files` (`silent`, `sound`,
`with_sound`, `player`), the `job_id`, `quoted_credits` and `charged_credits`,
and `sync`: `ok`, the `detected_onsets_s` exactly as printed, and the
`expected_impacts_s` labeled as expected. For any other status, report `status` and
`message` and the next command these rules allow.
