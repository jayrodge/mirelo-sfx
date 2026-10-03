#!/usr/bin/env python3
"""Add Mirelo sound effects to a silent video (Mirelo REST v3, API version 2026-08-28).

Subcommands: doctor | preflight | generate | resume. Every command prints one JSON object.
Stdlib only; needs Python 3.12+ and ffmpeg/ffprobe on PATH.
"""

import argparse
import array
import hashlib
import html
import json
import math
import mimetypes
import os
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import wave
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_URL = "https://api.mirelo.ai"
API_VERSION = "2026-08-28"
MODEL = "sfx-1.6"
PATHS = {
    "me": "/v3/me",
    "assets": "/v3/assets",
    "preflight": "/v3/video-to-sfx/generations/preflight",
    "create": "/v3/video-to-sfx/generations",
    "job": "/v3/video-to-sfx/generations/{id}",
}
CREATE_WAIT_S = 25
HTTP_TIMEOUT_S = 60
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 300
IDEMPOTENCY_RETENTION_S = 24 * 60 * 60
DEFAULT_MAX_CREDITS = None
DEFAULT_CREDENTIALS = Path.home() / ".config" / "mirelo" / "credentials"

TERMINAL = frozenset({"succeeded", "partially_succeeded", "failed", "canceled", "expired"})
SUCCESS = frozenset({"succeeded", "partially_succeeded"})
INSUFFICIENT_CODES = frozenset({"insufficient_credits", "no_active_subscription"})
MEDIA_REJECT_CODES = frozenset({"invalid_asset", "invalid_video", "video_format_unsupported",
                                "video_too_short", "video_url_unreachable", "payload_too_large"})
EXPIRED_DOWNLOAD = frozenset({400, 403, 404, 410})
OUTPUTS = {"silent": "silent.mp4", "sound": "sound.wav", "with_sound": "with-sound.mp4",
           "player": "player.html", "job": "job.json"}

Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]
_SECRETS: set[str] = set()


class MireloError(RuntimeError):
    def __init__(self, status: int, message: str, code: str | None = None) -> None:
        self.status, self.message, self.code = status, message, code
        super().__init__(f"HTTP {status}" + (f" {code}" if code else "") + f": {message}")


class UploadRejected(MireloError):
    pass


class InsufficientCredits(MireloError):
    pass


class DownloadExpired(MireloError):
    pass


class CredentialError(RuntimeError):
    pass


class CreditCapError(RuntimeError):
    pass


class UsageError(RuntimeError):
    pass


def scrub(text: str) -> str:
    for secret in _SECRETS:
        text = text.replace(secret, "[redacted]")
    return text


# ---------------------------------------------------------------- credentials

def credential_files() -> list[Path]:
    override = os.environ.get("MIRELO_CREDENTIALS")
    return [HERE / ".env", Path(override).expanduser() if override else DEFAULT_CREDENTIALS]


def _read_key(path: Path) -> str | None:
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise CredentialError(f"{path} must not be readable by others; run: chmod 600 {path}")
    for line in path.read_text().splitlines():
        name, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and name.strip() == "MIRELO_API_KEY":
            value = value.strip().strip("'\"")
            if value:
                return value
    return None


def load_api_key(env: dict[str, str] | None = None, files: list[Path] | None = None) -> tuple[str, str]:
    """Return (key, where it came from). The key itself is never printed or written."""
    env = os.environ if env is None else env
    files = credential_files() if files is None else files
    value = (env.get("MIRELO_API_KEY") or "").strip()
    if value:
        _SECRETS.add(value)
        return value, "env MIRELO_API_KEY"
    for path in files:
        if path.is_file() and (value := _read_key(path)):
            _SECRETS.add(value)
            return value, str(path)
    raise CredentialError("no Mirelo API key found. Set MIRELO_API_KEY, or add MIRELO_API_KEY=... to "
                          + " or ".join(str(p) for p in files) + " (chmod 600)")


# ---------------------------------------------------------------- HTTP client

def urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
        raise MireloError(0, f"network error: {getattr(e, 'reason', e)}") from None


def generation_body(asset_id: str, prompt: str | None, duration_ms: int) -> bytes:
    inp: dict = {"video": {"type": "asset", "id": asset_id}}
    if prompt:
        inp["prompt"] = prompt
    body = {"model": MODEL, "duration_ms": int(duration_ms), "num_variants": 1,
            "input": inp, "output": {"format": "wav"}}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def multipart(boundary: str, fields: dict[str, str], filename: str, content_type: str, data: bytes) -> bytes:
    out = bytearray()
    for name, value in fields.items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    out += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n").encode()
    return bytes(out + data + f"\r\n--{boundary}--\r\n".encode())


def parse_job(data: dict) -> dict:
    url = url_expires_at = None
    for output in (data.get("result") or {}).get("outputs") or []:
        for variant in output.get("variants") or []:
            audio = (variant.get("files") or {}).get("audio") if variant.get("status") == "succeeded" else None
            if audio and audio.get("url"):
                url, url_expires_at = audio["url"], audio.get("url_expires_at")
                break
        if url:
            break
    return {"id": data.get("id"), "status": data.get("status"), "download_url": url,
            "url_expires_at": url_expires_at, "credits": data.get("credits"),
            "errors": [{"code": e.get("code"), "message": e.get("message")} for e in data.get("errors") or []]}


class Client:
    def __init__(self, api_key: str, transport: Transport = urllib_transport, base_url: str = BASE_URL) -> None:
        _SECRETS.add(api_key)
        self._key, self._transport, self._base = api_key, transport, base_url.rstrip("/")

    def _call(self, method: str, path: str, payload: bytes | None = None,
              extra: dict[str, str] | None = None) -> tuple[int, bytes]:
        headers = {"Authorization": f"Bearer {self._key}", "Accept": "application/json",
                   "Mirelo-Version": API_VERSION, **(extra or {})}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        return self._transport(method, self._base + path, headers, payload)

    @staticmethod
    def _error(status: int, body: bytes, default: type[MireloError] = MireloError) -> MireloError:
        code, message = None, body[:200].decode("utf-8", "replace")
        try:
            err = json.loads(body)["error"]
            code, message = err.get("code"), err.get("message", "")
        except (ValueError, KeyError, TypeError):
            pass
        cls = default
        if status == 402 or code in INSUFFICIENT_CODES:
            cls = InsufficientCredits
        elif code in MEDIA_REJECT_CODES or status in (413, 422):
            cls = UploadRejected
        return cls(status, scrub(message), code)

    def _json(self, status: int, body: bytes, ok: tuple[int, ...], default=MireloError) -> dict:
        if status not in ok:
            raise self._error(status, body, default)
        return json.loads(body)

    def me(self) -> dict:
        return self._json(*self._call("GET", PATHS["me"]), (200,))

    def upload(self, path: Path) -> str:
        content_type = mimetypes.guess_type(path.name)[0] or ""
        if not content_type.startswith("video/"):
            raise UploadRejected(0, f"unsupported content type {content_type or 'unknown'!r} for {path.name}")
        ticket = self._json(*self._call("POST", PATHS["assets"], json.dumps({"content_type": content_type}).encode()),
                            (200, 201), UploadRejected)
        size = path.stat().st_size
        if size > int(ticket["max_bytes"]):
            raise UploadRejected(0, f"file is {size} bytes, over max_bytes {ticket['max_bytes']}")
        boundary = uuid.uuid4().hex
        form = multipart(boundary, ticket.get("fields") or {}, path.name, content_type, path.read_bytes())
        try:
            status, body = self._transport("POST", ticket["upload_url"],
                                           {"Content-Type": f"multipart/form-data; boundary={boundary}"}, form)
        except MireloError as e:
            raise UploadRejected(e.status, e.message) from None
        if not 200 <= status < 300:
            raise UploadRejected(status, "storage refused upload: " + body[:200].decode("utf-8", "replace"))
        return ticket["id"]

    def quote(self, asset_id: str, duration_ms: int, prompt: str | None = None) -> dict:
        data = self._json(*self._call("POST", PATHS["preflight"], generation_body(asset_id, prompt, duration_ms)),
                          (200,))
        rec = data.get("credit_recovery")
        affordable = None
        if rec is not None:
            affordable = (rec.get("provisioning_state") == "ready" and rec.get("recovery_action") is None
                          and (rec.get("credit_shortfall") or 0) == 0)
        return {"credits": int(data["credits"]), "estimated_ms": data.get("estimated_ms"), "affordable": affordable}

    def create_job(self, asset_id: str, prompt: str | None, idempotency_key: str, duration_ms: int,
                   request_body: str | None = None) -> dict:
        status, body = self._call("POST", f"{PATHS['create']}?wait={CREATE_WAIT_S}",
                                  request_body.encode() if request_body is not None else
                                  generation_body(asset_id, prompt, duration_ms), {"Idempotency-Key": idempotency_key})
        try:
            job = parse_job(self._json(status, body, (200, 202)))
        except (ValueError, TypeError, AttributeError):
            raise MireloError(0, "invalid generation response; submission may have been accepted") from None
        if not job["id"] or not job["status"]:
            raise MireloError(0, "generation response is missing job id or status; submission may have been accepted")
        return job

    def get_job(self, job_id: str) -> dict:
        return parse_job(self._json(*self._call("GET", PATHS["job"].format(id=job_id)), (200,)))

    def download(self, url: str, dest: Path) -> None:
        status, body = self._transport("GET", url, {}, None)
        if status in EXPIRED_DOWNLOAD:
            raise DownloadExpired(status, "download link expired; fetch the job again")
        if not 200 <= status < 300:
            raise MireloError(status, "download failed")
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(body)
        os.replace(tmp, dest)


# ---------------------------------------------------------------- media

def ffprobe(path: Path, *args: str) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-of", "json", *args, str(path)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def duration_s(path: Path) -> float:
    return float(ffprobe(path, "-show_entries", "format=duration")["format"]["duration"])


def duration_ms_for(seconds: float) -> int:
    whole = round(seconds)
    ms = whole * 1000 if abs(seconds - whole) <= 0.05 else int(seconds) * 1000
    return max(1000, ms)


def mux(video: Path, audio: Path, dest: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", str(dest)], check=True, capture_output=True)


def onsets(wav: Path, threshold_db: float = -30.0, rate: int = 16000, window_s: float = 0.02,
           quiet_s: float = 0.15) -> list[float]:
    with tempfile.TemporaryDirectory() as tmp:
        mono = Path(tmp) / "mono.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-ar", str(rate),
                        "-c:a", "pcm_s16le", str(mono)], check=True, capture_output=True)
        with wave.open(str(mono), "rb") as w:
            samples = array.array("h", w.readframes(w.getnframes()))
    window, quiet_needed = int(rate * window_s), math.ceil(quiet_s / window_s)
    quiet_run, found = quiet_needed, []
    for i in range(0, len(samples) - window + 1, window):
        rms = math.sqrt(sum(s * s for s in samples[i:i + window]) / window)
        if rms > 0 and 20 * math.log10(rms / 32768) >= threshold_db:
            if quiet_run >= quiet_needed:
                found.append(round(i / rate, 3))
            quiet_run = 0
        else:
            quiet_run += 1
    return found


PLAYER = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Mirelo SFX: before and after</title>
<style>body{{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:2rem}}
.pair{{display:flex;gap:1rem;flex-wrap:wrap}}figure{{margin:0;flex:1 1 480px}}video{{width:100%;background:#000}}
button{{font-size:1rem;padding:.5rem 1rem;margin:1rem 0}}pre{{background:#1e1e28;padding:1rem;white-space:pre-wrap}}</style>
</head><body><h1>Before and after</h1><div class="pair">
<figure><figcaption>Before (silent)</figcaption><video id="before" controls muted src="silent.mp4"></video></figure>
<figure><figcaption>After (Mirelo SFX)</figcaption><video id="after" controls src="with-sound.mp4"></video></figure>
</div><button id="both">Play both</button><pre>{notes}</pre>
<script>const b=document.getElementById("before"),a=document.getElementById("after");
document.getElementById("both").onclick=()=>{{b.currentTime=0;a.currentTime=0;b.play();a.play();}};
a.addEventListener("seeked",()=>{{b.currentTime=a.currentTime;}});</script></body></html>
"""


def finish_outputs(video: Path, out: Path, state: dict) -> dict:
    silent, sound, with_sound = out / OUTPUTS["silent"], out / OUTPUTS["sound"], out / OUTPUTS["with_sound"]
    if video.resolve() != silent.resolve():
        shutil.copyfile(video, silent)
    mux(silent, sound, with_sound)
    found = onsets(sound)
    sidecar = video.with_suffix(".json")
    sync: dict = {"detected_onsets_s": found}
    if sidecar.is_file():
        impacts = json.loads(sidecar.read_text())["impacts"]
        sync.update(expected_impacts_s=impacts, ok=all(any(abs(o - t) <= 0.1 for o in found) for t in impacts))
    notes = "\n".join([f"prompt: {state['prompt']}", f"job id: {state['job_id']}",
                       f"quoted credits: {state['quoted_credits']}", f"charged credits: {state['charged_credits']}",
                       f"sync ok: {sync.get('ok', 'not checked')}", f"detected sound onsets (s): {found}",
                       f"expected impacts (s): {sync.get('expected_impacts_s', 'none')}"])
    (out / OUTPUTS["player"]).write_text(PLAYER.format(notes=html.escape(notes)))
    return sync


# ---------------------------------------------------------------- job state and pipeline

def load_state(out: Path) -> dict | None:
    p = out / OUTPUTS["job"]
    return json.loads(p.read_text()) if p.is_file() else None


def save_state(out: Path, state: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / (OUTPUTS["job"] + ".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, out / OUTPUTS["job"])


def result(state: dict, out: Path, **extra) -> dict:
    keys = ("job_id", "status", "quoted_credits", "charged_credits", "message")
    return {"out": str(out), **{k: state.get(k) for k in keys if state.get(k) is not None or k != "message"}, **extra}


def check_quote(quote: dict, max_credits: int | None) -> None:
    if quote["affordable"] is False:
        raise InsufficientCredits(402, f"the Mirelo account cannot fund {quote['credits']} credits")
    if max_credits is not None and quote["credits"] > max_credits:
        raise CreditCapError(f"quote {quote['credits']} credits exceeds the {max_credits}-credit cap per job")


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def saved_video(state: dict) -> Path:
    """Use the exact uploaded bytes, even if the user's original was moved or replaced."""
    if not state.get("snapshot") or not state.get("snapshot_sha256"):
        raise UsageError("this run has no saved video snapshot; use a new --out for a fresh preflight")
    video = Path(state["snapshot"])
    if not video.is_file() or file_digest(video) != state["snapshot_sha256"]:
        raise UsageError("saved video snapshot is missing or changed; restore the original snapshot before retrying")
    sidecar = video.with_suffix(".json")
    expected = state.get("sidecar_sha256")
    if (expected is None and sidecar.exists()) or (expected is not None and
            (not sidecar.is_file() or file_digest(sidecar) != expected)):
        raise UsageError("saved sync sidecar is missing or changed; restore it before retrying")
    return video


def preflight(video: Path, out: Path, client, prompt: str | None = None, max_credits: int | None = DEFAULT_MAX_CREDITS,
              probe: Callable[[Path], float] = duration_s) -> dict:
    video = video.resolve()
    state = load_state(out)
    if state and state.get("job_id"):
        raise UsageError(f"job {state['job_id']} was already submitted in {out}; use resume or a new --out")
    if state and state.get("status") == "submitting":
        raise UsageError(f"a submission is pending in {out}; re-run generate with the same video and prompt")
    out.mkdir(parents=True, exist_ok=True)
    # Stage separately so a failed re-quote never overwrites the last quoted snapshot.
    with tempfile.TemporaryDirectory(prefix=".preflight-", dir=out) as staging:
        snapshot = Path(staging) / ("source" + video.suffix)
        shutil.copyfile(video, snapshot)
        sidecar = video.with_suffix(".json")
        staged_sidecar = snapshot.with_suffix(".json")
        if sidecar.is_file():
            shutil.copyfile(sidecar, staged_sidecar)
        snapshot_sha256 = file_digest(snapshot)
        sidecar_sha256 = file_digest(staged_sidecar) if staged_sidecar.is_file() else None
        duration_ms = duration_ms_for(probe(snapshot))
        asset_id = client.upload(snapshot)
        quote = client.quote(asset_id, duration_ms, prompt)
        check_quote(quote, max_credits)
        saved = out.resolve() / snapshot.name
        os.replace(snapshot, saved)
        saved.chmod(0o400)
        if sidecar_sha256 is not None:
            os.replace(staged_sidecar, saved.with_suffix(".json"))
            saved.with_suffix(".json").chmod(0o400)
        else:
            saved.with_suffix(".json").unlink(missing_ok=True)
    state = {"idempotency_key": str(uuid.uuid4()), "video": str(video), "prompt": prompt or "",
             "snapshot": str(saved), "snapshot_sha256": snapshot_sha256, "sidecar_sha256": sidecar_sha256,
             "request_body": generation_body(asset_id, prompt, duration_ms).decode(),
             "asset_id": asset_id, "duration_ms": duration_ms, "job_id": None, "status": "quoted",
             "quoted_credits": quote["credits"], "charged_credits": None, "message": None}
    save_state(out, state)
    return result(state, out, estimated_ms=quote["estimated_ms"], max_credits=max_credits)


def generate(video: Path, prompt: str, out: Path, client, max_credits: int | None = DEFAULT_MAX_CREDITS,
             poll_timeout: float = POLL_TIMEOUT_S, sleep: Callable[[float], None] = time.sleep,
             clock: Callable[[], float] = time.monotonic, probe: Callable[[Path], float] = duration_s,
             finish=finish_outputs) -> dict:
    video = video.resolve()
    state = load_state(out)
    if state and state.get("job_id"):
        raise UsageError(f"job {state['job_id']} was already submitted in {out}; run resume, never generate again")
    if state and state.get("status") == "submitting":
        if state["prompt"] != prompt or state["video"] != str(video):
            raise UsageError("a submission may already exist in this --out; re-run generate with the same "
                             "video and prompt so the idempotency key recovers it")
        submitted_at = state.get("submitted_at")
        if not isinstance(submitted_at, (int, float)) or not 0 <= time.time() - submitted_at < IDEMPOTENCY_RETENTION_S:
            raise UsageError("pending submission has an expired or unknown 24-hour idempotency window; "
                             "reconcile the original job with Mirelo before any new paid submission")
    elif state and state.get("status") == "quoted":
        if state["prompt"] != prompt or state["video"] != str(video):
            raise UsageError("video or prompt differs from the saved quote; run a fresh preflight with the "
                             "intended video and prompt, then run generate")
    else:
        preflight(video, out, client, prompt, max_credits, probe)
        state = load_state(out)
    if max_credits is not None and state["quoted_credits"] > max_credits:
        raise CreditCapError(f"quote {state['quoted_credits']} credits exceeds the {max_credits}-credit cap per job")

    snapshot = saved_video(state)
    submitted_at = state["submitted_at"] if state["status"] == "submitting" else time.time()
    state.update(status="submitting", message=None, submitted_at=submitted_at)
    save_state(out, state)
    try:
        job = client.create_job(state["asset_id"], state["prompt"], state["idempotency_key"],
                                state["duration_ms"], state["request_body"])
    except MireloError as e:
        if isinstance(e, UploadRejected) and 400 <= e.status < 500:
            state["status"] = "rejected"
        elif e.status == 402:
            state["status"] = "quoted"
        state["message"] = (f"{e}; re-run the same generate command to recover safely"
                            if state["status"] == "submitting" else str(e))
        save_state(out, state)
        raise
    state.update(job_id=job["id"], status=job["status"])
    save_state(out, state)
    return _poll_and_finish(state, job, snapshot, out, client, poll_timeout, sleep, clock, finish)


def resume(out: Path, client, poll_timeout: float = POLL_TIMEOUT_S, sleep: Callable[[float], None] = time.sleep,
           clock: Callable[[], float] = time.monotonic, finish=finish_outputs) -> dict:
    state = load_state(out)
    if state is None:
        raise UsageError(f"no job.json in {out}")
    if not state.get("job_id"):
        raise UsageError(f"no job was submitted from {out}; nothing to resume")
    if state["status"] == "done":
        return result(state, out, files=_files(out), sync=state.get("sync"))
    video = saved_video(state)
    job = client.get_job(state["job_id"])
    return _poll_and_finish(state, job, video, out, client, poll_timeout, sleep, clock, finish)


def _files(out: Path) -> dict:
    return {k: str(out / name) for k, name in OUTPUTS.items()}


def _poll_and_finish(state: dict, job: dict, video: Path, out: Path, client, poll_timeout: float,
                     sleep: Callable[[float], None], clock: Callable[[], float], finish) -> dict:
    deadline = clock() + poll_timeout
    while job["status"] not in TERMINAL:
        if clock() >= deadline:
            state.update(status="poll_timeout",
                         message=f"job {state['job_id']} still running after {poll_timeout:g}s; run resume")
            save_state(out, state)
            return result(state, out)
        sleep(POLL_INTERVAL_S)
        try:
            job = client.get_job(state["job_id"])
        except MireloError as e:
            if e.status in (0, 429) or e.status >= 500:
                continue
            raise

    state["charged_credits"] = job.get("credits")
    if job["status"] not in SUCCESS or not job.get("download_url"):
        state["status"] = job["status"] if job["status"] not in SUCCESS else "failed"
        state["message"] = ("; ".join(f"{e['code']}: {e['message']}" for e in job["errors"])
                            or f"job ended with status {job['status']} and no audio")
        save_state(out, state)
        return result(state, out)

    state["status"] = "downloading"
    save_state(out, state)
    sound = out / OUTPUTS["sound"]
    try:
        client.download(job["download_url"], sound)
    except DownloadExpired:
        fresh = client.get_job(state["job_id"])
        if not fresh.get("download_url"):
            raise
        client.download(fresh["download_url"], sound)

    sync = finish(saved_video(state), out, state)
    state.update(status="done", message=None, sync=sync)
    save_state(out, state)
    return result(state, out, files=_files(out), sync=sync)


# ---------------------------------------------------------------- doctor and CLI

def doctor(transport: Transport = urllib_transport) -> tuple[dict, bool]:
    checks: dict = {"python": sys.version.split()[0]}
    ok = sys.version_info >= (3, 12)
    for tool in ("ffmpeg", "ffprobe"):
        checks[tool] = shutil.which(tool) or "missing"
        ok &= checks[tool] != "missing"
    skill_dirs = {"openclaw": Path(os.environ.get("OPENCLAW_SKILLS_DIR") or Path.home() / ".openclaw" / "skills"),
                  "hermes": Path(os.environ.get("HERMES_SKILLS_DIR") or Path.home() / ".hermes" / "skills")}
    skill_paths = {agent: root / "mirelo-sfx" / "SKILL.md" for agent, root in skill_dirs.items()}
    checks["skills"] = {agent: str(path) if path.is_file() else "not installed"
                       for agent, path in skill_paths.items()}
    skill = skill_paths["openclaw"]
    checks["skill"] = str(skill) if skill.is_file() else "not installed (run ./setup.sh)"
    try:
        key, source = load_api_key()
        checks["key"] = f"found in {source}"
        me = Client(key, transport).me()
        checks["api"] = {k: me.get(k) for k in ("billing_mode", "provisioning_state", "credits_available",
                                                 "spend_capacity", "recovery_action")}
    except (CredentialError, MireloError) as e:
        checks.setdefault("key", "missing")
        checks["api"] = f"error: {scrub(str(e))}"
        ok = False
    return checks, ok


def _default_out() -> Path:
    return HERE / "runs" / time.strftime("%Y%m%d-%H%M%S")


def _video(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_file():
        raise UsageError(f"video not found: {p}")
    return p


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mirelo.py", description="Add Mirelo sound effects to a silent video.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="check Python, ffmpeg, the API key and API access (free)")
    for name, help_text in (("preflight", "upload the video and quote credits; free, submits nothing"),
                            ("generate", "PAID: upload, quote, check cost, submit one generation, and build outputs")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--video", required=True)
        p.add_argument("--prompt", required=(name == "generate"))
        p.add_argument("--out", help="run folder (default: runs/<timestamp> next to mirelo.py)")
        p.add_argument("--max-credits", type=int, default=DEFAULT_MAX_CREDITS,
                       help="optional per-job credit limit (default: no cap)")
    r = sub.add_parser("resume", help="keep polling/downloading a submitted job; never resubmits")
    r.add_argument("--out", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            checks, ok = doctor()
            print(json.dumps({"ok": ok, **checks}, indent=2))
            return 0 if ok else 1
        if getattr(args, "max_credits", None) is not None and args.max_credits < 0:
            raise UsageError("--max-credits must be non-negative")
        out = Path(args.out).expanduser().resolve() if args.out else _default_out()
        if args.command == "resume":
            data = resume(out, Client(load_api_key()[0]))
        elif args.command == "preflight":
            video = _video(args.video)
            data = preflight(video, out, Client(load_api_key()[0]), args.prompt, args.max_credits)
            gen = ["python3", str(Path(__file__).resolve()), "generate" if args.prompt else "preflight",
                   "--video", str(video.resolve()),
                   "--prompt", args.prompt or "<describe the sound>", "--out", str(out)]
            if args.max_credits is not None:
                gen += ["--max-credits", str(args.max_credits)]
            data["next"] = (("Optional paid generation command: " if args.prompt else
                             "Choose a sound description, then get a fresh free quote: ")
                            + shlex.join(gen))
        else:
            video = Path(args.video).expanduser()
            data = generate(video, args.prompt, out, Client(load_api_key()[0]), args.max_credits)
        print(scrub(json.dumps(data, indent=2)))
        return 0
    except (CredentialError, CreditCapError, UsageError, MireloError, OSError,
            subprocess.CalledProcessError) as e:
        print(scrub(json.dumps({"error": type(e).__name__, "message": str(e)}, indent=2)))
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": "KeyboardInterrupt", "message": "interrupted; if job.json has a job_id, "
                                                                    "run: mirelo.py resume --out DIR"}))
        return 130


if __name__ == "__main__":
    sys.exit(main())
