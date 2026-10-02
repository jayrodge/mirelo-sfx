# Mirelo SFX for OpenClaw

Give a silent video sound effects through your existing OpenClaw agent.
This skill calls Mirelo's hosted SFX API, then saves the audio, a video with
sound, and a before/after player. Audio generation happens in the cloud;
setup installs a skill for your current agent and requires no new model or agent.

**Requirements:** Python 3.12+, FFmpeg (including `ffprobe`), a Mirelo API
key with credits, and an existing OpenClaw installation for the agent workflow.
The CLI also works directly. Runtime uses Python's standard library: no pip
packages or virtual environment needed.

## Clone and set up

The repository is currently private; use an account with access when cloning.

```bash
git clone https://github.com/jayrodge/mirelo-sfx-openclaw.git ~/mirelo-sfx-openclaw
cd ~/mirelo-sfx-openclaw
./setup.sh
cp .env.example .env
chmod 600 .env
```

Open `.env` in your editor and set `MIRELO_API_KEY` by hand. Keep keys out of
agent prompts, chat messages, and shell commands/history. Get API access from
[Mirelo Developers](https://mirelo.ai/developers).

```bash
python3 mirelo.py doctor
```

`doctor` checks Python, FFmpeg, credentials and API access without generating
audio. `setup.sh` installs the skill in `~/.openclaw/skills/mirelo-sfx` and points
it at this clone. Keep the clone in place; rerun setup if you move it.

## Try the 8-second clip

First upload the clip and get a free credit quote:

```bash
python3 mirelo.py preflight \
  --video examples/silent.mp4 \
  --prompt "Add two soft rubber-ball impacts matching the visible bounces. Include a quiet room ambience."
```

Read `quoted_credits` and `out` in the JSON. After accepting the cost, run the
paid command using the **same video, prompt, and output folder**:

```bash
python3 mirelo.py generate \
  --video examples/silent.mp4 \
  --prompt "Add two soft rubber-ball impacts matching the visible bounces. Include a quiet room ambience." \
  --out <OUT_FROM_PREFLIGHT>
```

Open `player.html` from that folder in a browser. Each completed run contains
`silent.mp4`, `sound.wav`, `with-sound.mp4`, `player.html`, and `job.json`.

Or ask your existing OpenClaw agent:

> Add sound effects to ~/mirelo-sfx-openclaw/examples/silent.mp4 with this prompt:
> "Add two soft rubber-ball impacts matching the visible bounces. Include a quiet
> room ambience." Tell me the quoted cost first and wait for approval. Report
> sync onsets exactly as the JSON shows them.

Approve the quoted cost in a second message to generate. See the
[demo script](docs/demo.md) for a short presentation and fallback plan.

## Cost, recovery, and credentials

- `preflight` uploads your video to Mirelo and quotes credits; it starts no generation.
- `generate` spends credits. The installed agent skill asks for approval first.
  The CLI paid command assumes you have accepted the quote.
- Each job requests one variant and defaults to an 80-credit cap. Quotes above
  the cap or beyond the account's spend capacity are refused.
- A quote is bound to the saved video and prompt. If you change the sound
  description, run a fresh preflight and accept the new quote.
- If a submission response is lost, retry the exact same `generate` command.
  The saved request and key recover the original job. Recovery stops after
  24 hours, or if the submission age is unknown; reconcile the original job
  before deciding whether to start another paid generation.
- Polling stops after five minutes. If the result is `poll_timeout`, continue
  with `python3 mirelo.py resume --out <OUT_FROM_PREFLIGHT>`. Resume never
  resubmits a job. Use a fresh folder for a new generation or refinement.
- Keys are read from `MIRELO_API_KEY`, then `.env` beside `mirelo.py`, then
  `~/.config/mirelo/credentials`. Key files must be private, mode `600`.
  The tool does not print or persist the key in run outputs.
- `.env`, `runs/`, and `outputs/` are Git-ignored. Review generated files before
  sharing: they contain your video, prompt, and job metadata.

## Validation

On September 30, 2026, four agent-driven jobs succeeded at 80 credits each
(320 total). Generation turns took about 20–30 seconds. Two outputs passed
the clip's signal-based sync check; two failed. Jay approved run 1 after headphone playback on October 2, 2026.
Validation on the actual event image and presentation setup remains pending,
so these runs do not establish event Demo Ready status. Details and
presentation gates are in the [demo notes](docs/demo.md).

The tests mock Mirelo requests and spend no credits; FFmpeg exercises local
media processing. CI runs them on Python 3.12 and 3.14.

```bash
python3 -m pip install pytest  # test dependency only
python3 -m pytest -q tests
```
