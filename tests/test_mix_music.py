"""Exercise real media mixing and input/output preservation without API calls."""
import importlib.util
import math
from pathlib import Path
import shutil
import struct
import subprocess

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mix_music", REPO / "mix_music.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def media(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe required for media integration tests")
    video = tmp_path / "source.mp4"
    music = tmp_path / "music.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=32x32:d=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest", str(video)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=220:duration=1", str(music)], check=True)
    return video, music, tmp_path / "new/with-music.mp4"


def test_real_mix_preserves_inputs_and_video(media):
    video, music, out = media
    original = video.read_bytes(), music.read_bytes()
    result = module.mix(video, music, out)
    assert result["credits_spent"] == 0
    assert result["files"]["with_music"] == str(out)
    assert (video.read_bytes(), music.read_bytes()) == original
    measured = module.probe(out)
    assert abs(float(measured["format"]["duration"]) - 1.0) <= 0.05
    assert {s["codec_type"] for s in measured["streams"]} == {"video", "audio"}
    # Copying preserves the compressed video packet payload while audio changes.
    hashes = []
    for path in (video, out):
        hashes.append(subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                      "-map", "0:v", "-c", "copy", "-f", "hash", "-hash", "sha256", "-"],
                      check=True, capture_output=True).stdout)
    assert hashes[0] == hashes[1]
    # Both input tones must survive mixing. Stream existence alone would miss a
    # helper that dropped SFX or replaced it with music. Use the middle 0.8 s to
    # exclude AAC edge padding and correlate both sine/cosine phases.
    decoded = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(out), "-map", "0:a:0",
        "-ac", "1", "-ar", "8000", "-f", "s16le", "-",
    ], check=True, capture_output=True).stdout
    samples = [sample[0] / 32768 for sample in struct.iter_unpack("<h", decoded)][800:7200]
    assert len(samples) == 6400

    def tone_amplitude(frequency):
        cosine = sum(value * math.cos(2 * math.pi * frequency * i / 8000)
                     for i, value in enumerate(samples))
        sine = sum(value * math.sin(2 * math.pi * frequency * i / 8000)
                   for i, value in enumerate(samples))
        return 2 * math.hypot(cosine, sine) / len(samples)

    assert tone_amplitude(440) > 0.09  # Original SFX tone, input amplitude 0.125.
    assert tone_amplitude(220) > 0.07  # Backing tone, mixed at 0.8 gain.
    assert tone_amplitude(660) < 0.01  # Reject broad noise as a false positive.


def test_existing_output_is_not_replaced(media):
    video, music, out = media
    out.parent.mkdir()
    out.write_bytes(b"keep")
    with pytest.raises(ValueError, match="preserved"):
        module.mix(video, music, out)
    assert out.read_bytes() == b"keep"


def test_missing_input_writes_nothing(tmp_path):
    out = tmp_path / "out.mp4"
    with pytest.raises(ValueError, match="missing"):
        module.mix(tmp_path / "missing.mp4", tmp_path / "music.wav", out)
    assert not out.exists()


def test_music_requires_matching_duration(media):
    video, _, out = media
    with pytest.raises(ValueError, match="eight-second"):
        module.mix(video, module.DEFAULT_MUSIC, out)
    assert not out.exists()


def test_silent_video_rejected(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg required")
    video = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=32x32:d=1", str(video)], check=True)
    with pytest.raises(ValueError, match="generated SFX audio"):
        module.mix(video, module.DEFAULT_MUSIC, tmp_path / "out.mp4")
