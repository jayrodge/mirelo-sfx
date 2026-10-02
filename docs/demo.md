# A short Mirelo SFX demo

**Show the silent Artemis I liftoff, describe the roar, then compare sound designs.**
Keep the approved ball result as a pre-generated fallback; live generation is a bonus. This demonstrates a
hosted audio tool used by an existing OpenClaw agent.

## Before presenting

1. Run `python3 mirelo.py doctor` and confirm API access and spend capacity.
2. Prepare the approved ball run 1 as a known-good output folder with all five files: `silent.mp4`,
   `sound.wav`, `with-sound.mp4`, `player.html`, and `job.json`. Keep it under
   `outputs/fallback/` (Git-ignored). The repo also includes an Artemis video
   with Mirelo-generated sound; listen to it on the presentation machine.
3. Open its `player.html` and listen on headphones. Check the sound at both
   visible impacts and playback on the presentation machine.
4. Name a station owner and provide headphones. Without a listening setup
   and a completed headphone review, keep the demo out of a crowded-floor slot.

## Present it

The default `examples/artemis-liftoff.mp4` shows the real Artemis I launch:
eight seconds, 1280×720 at 30 fps, with the original audio removed. It uses
55.0–63.0 seconds of the NASA/Sam Lott source. See
[source and clip details](../examples/README.md). Any generated audio is Mirelo
sound design, not the actual NASA recording. The bundled
[`examples/artemis-liftoff-mirelo.mp4`](../examples/artemis-liftoff-mirelo.mp4)
is a completed sound design; it plays without API access or credits.

1. Play the silent clip. Say: “The agent can use a sound tool to add effects
   that follow the video.”
2. Play the bundled Artemis sound design with headphones and compare it with
   the silent launch. Keep the approved ball player as the validated fallback.
3. If there is time for one live generation within the 80-credit cap, ask the agent:

   > Add sound effects to ~/mirelo-sfx-openclaw/examples/artemis-liftoff.mp4 with this
   > prompt: "Deep rocket-engine rumble builds with the bright exhaust plume, swelling into a powerful sustained roar as the rocket lifts off. No speech, countdown, music, or extra explosions." Report the cost and
   > sync onsets exactly as the JSON shows them.

4. The agent generates directly, checking the quote and cap internally. Compare the
   result with the silent launch clip. Listen for the rumble and lift-off swell.
   The launch has no impact-timing sidecar: timing is not automatically checked
   and `sync.ok` is omitted. Watch and listen to assess alignment. Report
   detected onsets and any sync fields exactly as printed; `estimated_ms` is an estimate, not elapsed time.

For direct CLI use, follow the [README commands](../README.md#try-the-artemis-i-liftoff-clip).
If polling times out, run `python3 mirelo.py resume --out <OUT_FROM_JSON>`.
If the network stalls or the live sound design is weak, return to the prepared ball
player. Each explicitly requested refinement is a new quote and paid job. Do not
automatically iterate during a presentation. For a cost-only request, use
`preflight`, report the quote and stop without generating.

## What has been tested

On October 2, 2026, one direct `generate` command on dspark internally quoted
and submitted one Artemis job. Quote and actual charge were 80 credits;
the complete CLI command took 16.40 seconds. The result is eight seconds of
H.264 video with mono AAC audio at 44,100 Hz. Detected onsets were `[0.0]`;
`sync.ok` is omitted because the launch has no expected-impact sidecar.
These are execution/media checks, not headphone approval or event qualification.
The updated skill is installed; a fresh agent check waits for the separate
OpenClaw gateway repair.

These four runs used the retained `examples/silent.mp4` ball fixture, not the
Artemis video. Its expected impacts occur at 2.0 s and 5.0 s, as recorded in
`examples/silent.json`; these are not measured audio onsets.

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

Run 1 used:

> Add two soft rubber-ball impacts matching the visible bounces. Include a quiet
> room ambience.

Run 3 used:

> Two cartoony springy boing sounds, one on each bounce, playful and bright,
> no background music.

Runs 1 and 3 are candidates for the pre-generated fallback. The built-in
detector checks for an onset within ±100 ms of each expected impact; a passing
result does not establish perceptual sound quality. Busy prompts and a softer
refinement produced failing sync checks in this small sample.

**Headphone review: run 1 approved by Jay on October 2, 2026.** Use run 1 as
the fallback. Event Demo Ready is not established: validate the event image,
network, presentation playback and operator rehearsal before promotion.
