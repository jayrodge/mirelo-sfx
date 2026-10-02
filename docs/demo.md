# A short Mirelo SFX demo

**Show one silent clip, describe its sound, then compare the result.** Use a
pre-generated example first; live generation is a bonus. This demonstrates a
hosted audio tool used by an existing OpenClaw agent.

## Before presenting

1. Run `python3 mirelo.py doctor` and confirm API access and spend capacity.
2. Prepare a known-good output folder with all five files: `silent.mp4`,
   `sound.wav`, `with-sound.mp4`, `player.html`, and `job.json`. Keep it under
   `outputs/fallback/` (Git-ignored). Generated audio is not bundled with this repo.
3. Open its `player.html` and listen on headphones. Check the sound at both
   visible impacts and playback on the presentation machine.
4. Name a station owner and provide headphones. Without a listening setup
   and a completed headphone review, keep the demo out of a crowded-floor slot.

## Present it

The included `examples/silent.mp4` is eight seconds long, 1280×720 at 30 fps.
The ball impacts occur at **2.0 s and 5.0 s** (expected times from
`examples/silent.json`, not measured audio onsets).

1. Play the silent clip. Say: “The agent can use a sound tool to add effects
   that follow the video.”
2. Play the prepared before/after result with headphones.
3. If there is time and an approved credit budget, ask the agent:

   > Add sound effects to ~/mirelo-sfx-openclaw/examples/silent.mp4 with this
   > prompt: "Add two soft rubber-ball impacts matching the visible bounces.
   > Include a quiet room ambience." Tell me the quoted cost first and wait
   > for approval. Report sync onsets exactly as the JSON shows them.

4. Read the actual quote, approve it, and let the agent generate. Compare the
   result with the silent clip. Report detected onsets and `sync.ok` exactly
   as printed; `estimated_ms` is an estimate, not elapsed time.

For direct CLI use, follow the [README commands](../README.md#try-the-8-second-clip).
If polling times out, run `python3 mirelo.py resume --out <OUT_FROM_PREFLIGHT>`.
If the network stalls or a result misses the impacts, return to the prepared
player. Every refinement is a new quote and paid job; avoid an open-ended
refinement loop during a presentation.

## What has been tested

Recorded on September 30, 2026, on dspark through OpenClaw's `main` agent
using `vllm/nvidia/Qwen3.6-35B-A3B-NVFP4`. Audio generation used Mirelo's hosted
API. Four jobs succeeded, each quoted and charged 80 credits (320 total).
Generation turns took 19.6–28.0 seconds; this is measured agent wall time,
not Mirelo's estimate or a guarantee for future runs.

| Run | Sound description | Detected onsets (seconds) | `sync.ok` |
| --- | --- | --- | --- |
| 1 | Soft rubber-ball impacts, quiet room | `[1.96, 5.02]` | `true` |
| 2 | Basketball, sneaker squeak, gym echo | `[2.06, 3.66, 4.6]` | `false` |
| 3 | Two cartoony boings, no music | `[1.96, 5.04]` | `true` |
| 4 | Softer impacts, reduced ambience | `[2.12, 5.14]` | `false` |

Run 1 used the exact prompt above. Run 3 used:

> Two cartoony springy boing sounds, one on each bounce, playful and bright,
> no background music.

Runs 1 and 3 are candidates for the pre-generated fallback. The built-in
detector checks for an onset within ±100 ms of each expected impact; a passing
result does not establish perceptual sound quality. Busy prompts and a softer
refinement produced failing sync checks in this small sample.

**Headphone review: run 1 approved by Jay on October 2, 2026.** Use run 1 as
the fallback. Event Demo Ready is not established: validate the event image,
network, presentation playback and operator rehearsal before promotion.
