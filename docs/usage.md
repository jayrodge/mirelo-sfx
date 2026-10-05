# Usage and troubleshooting

## Quick start

```bash
git clone https://github.com/jayrodge/mirelo-sfx.git ~/mirelo-sfx
cd ~/mirelo-sfx
./setup.sh --agent openclaw
# Or, for Hermes: ./setup.sh --agent hermes
cp -n .env.example .env
chmod 600 .env
```

Open `.env` in your editor and set `MIRELO_API_KEY` by hand. Keep keys out of
agent prompts, chat messages, and shell commands/history. Get API access from
[Mirelo Developers](https://mirelo.ai/developers).

```bash
python3 mirelo.py doctor
```

`doctor` checks Python, FFmpeg, credentials and API access without generating
audio. The installer prints the installed skill path:

| Agent | Install command | Default skill folder |
| --- | --- | --- |
| OpenClaw | `./setup.sh --agent openclaw` | `~/.openclaw/skills/mirelo-sfx` |
| Hermes | `./setup.sh --agent hermes` | `~/.hermes/skills/mirelo-sfx` |

Open a fresh chat in your existing agent after installation. Keep the clone in
place; rerun setup if you move it. Setup changes no agent version, model,
gateway or config. The skill stays named `mirelo-sfx` for both agents.

For a custom skills directory, set `OPENCLAW_SKILLS_DIR` or
`HERMES_SKILLS_DIR` for the selected agent. Hermes installation deliberately
uses the native `~/.hermes` home rather than an inherited `HERMES_HOME`:
this matches the Build-a-Claw browser/terminal setup. If using another Hermes
profile, point `HERMES_SKILLS_DIR` at that profile's actual skills folder.

The agent's terminal must have access to Python 3.12+, FFmpeg, this clone and
the key file. A Docker or remote terminal needs those inside its execution
environment. `doctor` reports skill-folder checks for both agents; a found
skill file confirms installation, while a successful chat turn confirms use.

## Try the alien-shooter game clip

The default is eight seconds of original arcade gameplay: a player spaceship
moves and shoots, three enemies explode, and the score climbs. The large hit
flashes and isolated sound bursts make the picture-to-sound connection clear.
See [clip details](../examples/README.md).

[![Alien-shooter arcade gameplay](../examples/alien-shooter.jpg)](../examples/alien-shooter.mp4)

[Watch the example with Mirelo-generated sound](../examples/alien-shooter-mirelo.mp4).
This pre-generated sample plays without API access or spending credits.
Check it on your presentation speaker before using it in a crowded room.

Generate one sound design with one command. It uploads the clip, quotes the
cost, checks affordability, then submits one variant:

```bash
python3 mirelo.py generate \
  --video examples/alien-shooter.mp4 \
  --prompt "Three powerful arcade laser-blast explosions synchronized to the three enemy hits at 1.8, 4.0, and 6.2 seconds. Each burst has a crisp electronic zap and crunchy explosive hit with a short decay. Quiet between bursts. No music, speech, ambience or extra shots."
```

Read the cost, status and `out` in the JSON. Open `player.html` from that
folder in a browser. Each completed run contains `silent.mp4`, `sound.wav`,
`with-sound.mp4`, `player.html`, and `job.json`.

Or ask your existing OpenClaw or Hermes agent in a fresh chat:

> Add sound effects to ~/mirelo-sfx/examples/alien-shooter.mp4 with this prompt:
> "Three powerful arcade laser-blast explosions synchronized to the three enemy hits at 1.8, 4.0, and 6.2 seconds. Each burst has a crisp electronic zap and crunchy explosive hit with a short decay. Quiet between bursts. No music, speech, ambience or extra shots." Report credits and detected onsets exactly as the JSON prints them.

[Play the arcade game locally](../examples/play-game.html): arrow keys move,
Space fires, R restarts and M toggles sound. Each enemy hit plays a burst cut
from this Mirelo result. The game and sound playback work offline and spend
no credits. Download the clone first; GitHub's file view does not run HTML.

For audience participation, play the silent gameplay and let someone describe
the sound style: for example, retro laser, comic-book blast, or futuristic
cannon. Ask the agent for that one sound design, then compare the result.
The bundled sample is one laser-blast design; other styles require their own
explicit generation request.

An explicit generation or refinement request authorizes one paid job. There
is no default credit cap; the available balance still limits spending. See the [demo script](demo.md) for the presentation
sequence and fallback. The [Artemis launch sample](../examples/artemis-liftoff-mirelo.mp4)
remains available as an alternative.

## Cost, recovery, and credentials

- `preflight` uploads your video to Mirelo and quotes credits; it starts no generation.
- `generate` spends credits after its internal quote and affordability check.
  The installed agent skill runs it directly for an explicit generation request.
  For cost-only requests, use `preflight` and stop after the quote.
- Each job requests one variant. There is no default credit cap. Quotes
  beyond the account's spend capacity are refused. Add `--max-credits 80`
  only when you want an explicit 80-credit limit; a quote above a requested
  limit stops before submission.
- A quote is bound to the saved video and prompt. If you change the sound
  description, run `generate` with the new prompt in a new folder; it quotes
  those inputs before submitting.
  Requested refinements use a new folder; the agent never automatically iterates.
- If a submission response is lost, retry the exact same `generate` command.
  The saved request and key recover the original job. Recovery stops after
  24 hours, or if the submission age is unknown; reconcile the original job
  before deciding whether to start another paid generation.
- Polling stops after five minutes. If the result is `poll_timeout`, continue
  with `python3 mirelo.py resume --out <OUT_FROM_JSON>`. Resume never
  resubmits a job. Use a fresh folder for a new generation or refinement.
- Keys are read from `MIRELO_API_KEY`, then `.env` beside `mirelo.py`, then
  `~/.config/mirelo/credentials`. Key files must be private, mode `600`.
  The tool does not print or persist the key in run outputs.
- `.env`, `runs/`, and `outputs/` are Git-ignored. Review generated files before
  sharing: they contain your video, prompt, and job metadata.


## Tests

The suite mocks Mirelo requests and exercises media processing with FFmpeg.

```bash
python3 -m pip install pytest
python3 -m pytest -q tests
```
