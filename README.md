# Mirelo SFX for OpenClaw

Ask your OpenClaw agent to add sound effects to a silent video. The skill calls
[Mirelo](https://mirelo.ai/developers) SFX 1.6 and returns `sound.wav`,
`with-sound.mp4`, and a before/after `player.html`.

Needs Python 3.12+ and FFmpeg. No pip installs: `mirelo.py` is one stdlib-only file.

## Quick start

```bash
git clone <this repo> ~/mirelo-sfx-openclaw && cd ~/mirelo-sfx-openclaw
./setup.sh                                  # copies the skill into ~/.openclaw/skills/mirelo-sfx
cp .env.example .env && chmod 600 .env      # then put your key after MIRELO_API_KEY=
python3 mirelo.py doctor                    # key found, FFmpeg present, API reachable
```

Try it (the quote is free; `generate` spends credits):

```bash
python3 mirelo.py preflight --video examples/silent.mp4 --prompt "Two soft rubber-ball impacts, quiet room"
python3 mirelo.py generate  --video examples/silent.mp4 --prompt "Two soft rubber-ball impacts, quiet room" --out <out from preflight>
```

Then open `runs/<id>/player.html` in a browser for the before/after comparison.

Or ask the agent: *"Add sound effects to ~/mirelo-sfx-openclaw/examples/silent.mp4. Tell me the cost first."*

## How it behaves

- `preflight` uploads the video and returns the credit quote. It never starts a job.
- Each job is capped at 80 credits (`--max-credits` to change) and is refused if the account can't fund it. Always one variant.
- `generate` polls for up to 5 minutes. On timeout, `resume --out <dir>` picks the job up from `job.json` without resubmitting.
- Each run folder holds `silent.mp4`, `sound.wav`, `with-sound.mp4`, `player.html`, and `job.json`.

The API key is read from `MIRELO_API_KEY`, then `.env` next to `mirelo.py`, then
`~/.config/mirelo/credentials`. Key files must be mode 600. The key is never printed or written.

`examples/silent.mp4` is an 8 s, 1280x720, 30 fps bouncing ball with impacts at 2.0 s and 5.0 s
(`examples/silent.json`), used for a simple sync check.

## Tests

```bash
python3 -m pytest -q tests        # or: uvx pytest -q tests
```
