import json
import math
import os
import shlex
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import mirelo  # noqa: E402

KEY = "sk-test-SECRET-0123456789"
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                  reason="ffmpeg/ffprobe not installed")


def job_body(status, url=None, credits=None, errors=None):
    variants = [{"status": "succeeded", "files": {"audio": {"url": url, "url_expires_at": "t"}}}] if url else []
    return {"id": "gen_1", "status": status, "credits": credits, "errors": errors or [],
            "result": {"outputs": [{"variants": variants}]}}


class FakeHTTP:
    """Scripted Mirelo API. Records every request; never touches the network."""

    def __init__(self, credits=80, shortfall=0, create=None, polls=None, downloads=None, wav=b"RIFF"):
        self.credits, self.shortfall = credits, shortfall
        self.create = create or (202, job_body("queued"))
        self.polls = list(polls or [job_body("running")])
        self.downloads = list(downloads or [])
        self.wav = wav
        self.requests = []

    def count(self, method, fragment):
        return sum(1 for m, u, _, _ in self.requests if m == method and fragment in u)

    def __call__(self, method, url, headers, body):
        self.requests.append((method, url, headers, body))
        if url.endswith("/v3/assets"):
            return 201, json.dumps({"id": "asset_1", "upload_url": "https://storage/up", "max_bytes": 10**8,
                                    "fields": {"key": "k1", "policy": "p1"}}).encode()
        if url == "https://storage/up":
            return 204, b""
        if url.endswith("/preflight"):
            rec = {"credit_shortfall": self.shortfall, "recovery_action": "view_plans" if self.shortfall else None,
                   "provisioning_state": "ready"}
            return 200, json.dumps({"credits": self.credits, "estimated_ms": 15290, "credit_recovery": rec}).encode()
        if method == "POST" and "/generations?wait=25" in url:
            status, data = self.create
            return status, json.dumps(data).encode()
        if method == "GET" and "/generations/gen_1" in url:
            nxt = self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]
            return 200, json.dumps(nxt).encode()
        if url.startswith("https://dl/"):
            return (403, b"expired") if self.downloads and self.downloads.pop(0) == "expired" else (200, self.wav)
        if url.endswith("/v3/me"):
            return 200, json.dumps({"billing_mode": "metered", "credits_available": 5000}).encode()
        raise AssertionError(f"unexpected request {method} {url}")


class Clock:
    t = 0.0

    def sleep(self, s):
        self.t += s

    def __call__(self):
        return self.t


def no_finish(video, out, state):
    return {"detected_onsets_s": []}


@pytest.fixture
def run(tmp_path):
    video = tmp_path / "in" / "silent.mp4"
    video.parent.mkdir()
    video.write_bytes(b"video")
    out = tmp_path / "runs" / "1"
    clock = Clock()

    def _run(cmd, http, **kw):
        client = mirelo.Client(KEY, http)
        if cmd == "preflight":
            return mirelo.preflight(video, out, client, probe=lambda p: 8.0, **kw)
        if cmd == "generate":
            return mirelo.generate(video, kw.pop("prompt", "two bounces"), out, client, sleep=clock.sleep,
                                   clock=clock, probe=lambda p: 8.0, finish=kw.pop("finish", no_finish), **kw)
        return mirelo.resume(out, client, sleep=clock.sleep, clock=clock, finish=kw.pop("finish", no_finish), **kw)

    _run.out, _run.clock, _run.video = out, clock, video
    return _run


# ---- credentials

def test_key_lookup_order_env_then_env_file_then_credentials(tmp_path):
    env_file, creds = tmp_path / ".env", tmp_path / "credentials"
    creds.write_text("MIRELO_API_KEY=from-creds\n")
    creds.chmod(0o600)
    assert mirelo.load_api_key({}, [env_file, creds]) == ("from-creds", str(creds))
    env_file.write_text("# comment\nexport MIRELO_API_KEY='from-dotenv'\n")
    env_file.chmod(0o600)
    assert mirelo.load_api_key({}, [env_file, creds])[0] == "from-dotenv"
    assert mirelo.load_api_key({"MIRELO_API_KEY": "from-env"}, [env_file, creds])[0] == "from-env"


def test_empty_env_file_falls_through_and_open_mode_is_refused(tmp_path):
    env_file, creds = tmp_path / ".env", tmp_path / "credentials"
    env_file.write_text("MIRELO_API_KEY=\n")
    env_file.chmod(0o600)
    creds.write_text(f"MIRELO_API_KEY={KEY}\n")
    creds.chmod(0o644)
    with pytest.raises(mirelo.CredentialError, match="chmod 600") as e:
        mirelo.load_api_key({"MIRELO_API_KEY": "  "}, [env_file, creds])
    assert KEY not in str(e.value)


def test_missing_key_cli_exits_nonzero_without_leaking(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MIRELO_API_KEY", raising=False)
    monkeypatch.setenv("MIRELO_CREDENTIALS", str(tmp_path / "nope"))
    monkeypatch.setattr(mirelo, "HERE", tmp_path)
    code = mirelo.main(["preflight", "--video", str(REPO / "examples" / "silent.mp4"), "--out", str(tmp_path / "o")])
    err = json.loads(capsys.readouterr().out)
    assert code == 2 and err["error"] == "CredentialError" and "MIRELO_API_KEY" in err["message"]
    assert not (tmp_path / "o").exists()


def test_key_is_scrubbed_from_api_errors():
    def echo(method, url, headers, body):
        return 401, json.dumps({"error": {"code": "unauthorized", "message": f"bad key {KEY}"}}).encode()
    with pytest.raises(mirelo.MireloError) as e:
        mirelo.Client(KEY, echo).me()
    assert KEY not in str(e.value) and "[redacted]" in str(e.value)


# ---- request shape

def test_preflight_uploads_then_quotes_and_never_creates(run):
    http = FakeHTTP()
    res = run("preflight", http)
    assert res["status"] == "quoted" and res["quoted_credits"] == 80 and res["job_id"] is None
    assert http.count("POST", "/generations?wait") == 0
    (_, _, h1, b1), (m2, u2, h2, b2), (_, _, h3, b3) = http.requests
    assert h1["Authorization"] == f"Bearer {KEY}" and h1["Mirelo-Version"] == "2026-08-28"
    assert json.loads(b1) == {"content_type": "video/mp4"}
    assert m2 == "POST" and "Authorization" not in h2
    assert b2.index(b'name="key"') < b2.index(b'name="policy"') < b2.index(b'name="file"')
    body = json.loads(b3)
    assert body["model"] == "sfx-1.6" and body["num_variants"] == 1 and body["duration_ms"] == 8000
    assert body["input"]["video"] == {"type": "asset", "id": "asset_1"}
    assert json.loads((run.out / "job.json").read_text())["asset_id"] == "asset_1"


def test_fresh_generate_quotes_before_exactly_one_create_with_same_body(run):
    http = FakeHTTP(create=(200, job_body("succeeded", url="https://dl/a.wav", credits=80)))
    assert run("generate", http)["status"] == "done"
    quotes = [r for r in http.requests if r[1].endswith("/preflight")]
    creates = [r for r in http.requests if "/generations?wait=25" in r[1]]
    assert len(quotes) == len(creates) == 1
    quote, create = quotes[0], creates[0]
    assert http.requests.index(quote) < http.requests.index(create)
    assert quote[3] == create[3] and json.loads(create[3])["num_variants"] == 1
    assert create[2]["Idempotency-Key"] == json.loads((run.out / "job.json").read_text())["idempotency_key"]


# ---- cap and affordability

def test_quote_over_cap_is_refused_before_create(run):
    http = FakeHTTP(credits=81)
    with pytest.raises(mirelo.CreditCapError, match="81.*80"):
        run("generate", http)
    assert http.count("POST", "/generations?wait") == 0 and not (run.out / "job.json").exists()


def test_cap_override_allows_larger_quote(run):
    http = FakeHTTP(credits=120, create=(200, job_body("succeeded", url="https://dl/a.wav", credits=120)))
    assert run("generate", http, max_credits=120)["status"] == "done"


def test_saved_quote_is_rechecked_against_cap_at_generate(run):
    run("preflight", FakeHTTP(credits=120), prompt="two bounces", max_credits=200)
    http = FakeHTTP(credits=120)
    with pytest.raises(mirelo.CreditCapError):
        run("generate", http)
    assert http.requests == []


def test_unaffordable_quote_is_refused(run):
    http = FakeHTTP(shortfall=30)
    with pytest.raises(mirelo.InsufficientCredits):
        run("preflight", http)
    assert not (run.out / "job.json").exists()


def test_402_at_create_returns_to_quoted(run):
    err = {"error": {"code": "insufficient_credits", "message": "need 80"}}
    with pytest.raises(mirelo.InsufficientCredits):
        run("generate", FakeHTTP(create=(402, err)))
    state = json.loads((run.out / "job.json").read_text())
    assert state["status"] == "quoted" and state["job_id"] is None


# ---- no resubmit

def test_poll_timeout_then_resume_never_resubmits(run):
    http = FakeHTTP(polls=[job_body("running")])
    res = run("generate", http)
    assert res["status"] == "poll_timeout" and run.clock.t >= 300
    with pytest.raises(mirelo.UsageError, match="resume"):
        run("generate", http)
    http.polls = [job_body("succeeded", url="https://dl/a.wav", credits=80)]
    assert run("resume", http)["status"] == "done"
    assert http.count("POST", "/generations?wait") == 1


def test_network_drop_on_create_retries_with_same_key_only_for_same_prompt(run):
    http = FakeHTTP()
    http.create = None

    def drop(method, url, headers, body):
        if "/generations?wait" in url and http.create is None:
            http.requests.append((method, url, headers, body))
            raise mirelo.MireloError(0, "network error: timed out")
        return FakeHTTP.__call__(http, method, url, headers, body)

    with pytest.raises(mirelo.MireloError):
        run("generate", drop)
    with pytest.raises(mirelo.UsageError, match="same"):
        run("generate", drop, prompt="different")
    with pytest.raises(mirelo.UsageError, match="pending"):
        run("preflight", drop)
    http.create = (200, job_body("succeeded", url="https://dl/a.wav", credits=80))
    assert run("generate", drop)["status"] == "done"
    keys = {r[2]["Idempotency-Key"] for r in http.requests if "/generations?wait" in r[1]}
    assert len(keys) == 1
    assert len({r[3] for r in http.requests if "/generations?wait" in r[1]}) == 1


@pytest.mark.parametrize("status", [400, 401, 429, 500, 502, 503, 504])
def test_ambiguous_create_error_blocks_requote_and_reuses_exact_request(run, status, monkeypatch):
    http = FakeHTTP(create=(status, {"error": {"code": "unknown", "message": "try later"}}))
    with pytest.raises(mirelo.MireloError):
        run("generate", http)
    state = mirelo.load_state(run.out)
    assert state["status"] == "submitting" and state["job_id"] is None
    count = len(http.requests)
    with pytest.raises(mirelo.UsageError, match="pending"):
        run("preflight", http, prompt="changed")
    with pytest.raises(mirelo.UsageError, match="same"):
        run("generate", http, prompt="changed")
    assert len(http.requests) == count
    # The saved request must survive even a later script model default change.
    monkeypatch.setattr(mirelo, "MODEL", "future-default")
    http.create = (200, job_body("succeeded", url="https://dl/a.wav", credits=80))
    assert run("generate", http)["status"] == "done"
    creates = [r for r in http.requests if "/generations?wait" in r[1]]
    assert len(creates) == 2
    assert creates[0][2]["Idempotency-Key"] == creates[1][2]["Idempotency-Key"] == state["idempotency_key"]
    assert creates[0][3] == creates[1][3] == state["request_body"].encode()


@pytest.mark.parametrize("response", [{}, {"id": "gen_1"}, None])
def test_malformed_create_success_keeps_submission_guard(run, response):
    http = FakeHTTP(create=(200, response))
    with pytest.raises(mirelo.MireloError, match="submission may have been accepted"):
        run("generate", http)
    assert mirelo.load_state(run.out)["status"] == "submitting"
    count = len(http.requests)
    with pytest.raises(mirelo.UsageError, match="pending"):
        run("preflight", http)
    assert len(http.requests) == count


@pytest.mark.parametrize("age", [24 * 60 * 60, 25 * 60 * 60, None])
def test_expired_or_legacy_submission_refuses_retry_and_requote(run, age, monkeypatch):
    now = 1_000_000.0
    monkeypatch.setattr(mirelo.time, "time", lambda: now)
    http = FakeHTTP(create=(503, {"error": {"message": "try later"}}))
    with pytest.raises(mirelo.MireloError):
        run("generate", http)
    state = mirelo.load_state(run.out)
    assert state["submitted_at"] == now
    if age is None:
        state.pop("submitted_at")
        mirelo.save_state(run.out, state)
    else:
        monkeypatch.setattr(mirelo.time, "time", lambda: now + age)
    count = len(http.requests)
    with pytest.raises(mirelo.UsageError, match="24-hour.*reconcile"):
        run("generate", http)
    with pytest.raises(mirelo.UsageError, match="pending"):
        run("preflight", http)
    assert len(http.requests) == count and mirelo.load_state(run.out) == state


def test_immediate_submission_retry_keeps_first_epoch_key_and_body(run, monkeypatch):
    now = 1_000_000.0
    monkeypatch.setattr(mirelo.time, "time", lambda: now)
    http = FakeHTTP(create=(503, {"error": {"message": "try later"}}))
    with pytest.raises(mirelo.MireloError):
        run("generate", http)
    initial = mirelo.load_state(run.out)
    monkeypatch.setattr(mirelo.time, "time", lambda: now + 1)
    http.create = (200, job_body("succeeded", url="https://dl/a.wav", credits=80))
    assert run("generate", http)["status"] == "done"
    saved = mirelo.load_state(run.out)
    assert saved["submitted_at"] == initial["submitted_at"] == now
    creates = [r for r in http.requests if "/generations?wait" in r[1]]
    assert creates[0][2]["Idempotency-Key"] == creates[1][2]["Idempotency-Key"]
    assert creates[0][3] == creates[1][3]


@pytest.mark.parametrize("initial_prompt", [None, "original prompt"])
def test_prompt_change_requires_fresh_quote_then_generate(run, initial_prompt):
    http = FakeHTTP(create=(200, job_body("succeeded", url="https://dl/a.wav", credits=80)))
    run("preflight", http, prompt=initial_prompt)
    initial = mirelo.load_state(run.out)
    count = len(http.requests)
    with pytest.raises(mirelo.UsageError, match="fresh preflight.*then run generate"):
        run("generate", http, prompt="new prompt")
    assert len(http.requests) == count and mirelo.load_state(run.out) == initial
    run("preflight", http, prompt="new prompt")
    assert mirelo.load_state(run.out)["idempotency_key"] != initial["idempotency_key"]
    assert run("generate", http, prompt="new prompt")["status"] == "done"
    quote = [r for r in http.requests if r[1].endswith("/preflight")][-1]
    create = next(r for r in http.requests if "/generations?wait" in r[1])
    assert quote[3] == create[3]


def test_promptless_cli_quote_next_command_requotes(tmp_path, monkeypatch, capsys):
    video = tmp_path / "silent.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(mirelo, "load_api_key", lambda: (KEY, "test"))
    monkeypatch.setattr(mirelo, "preflight", lambda *args: {"quoted_credits": 80})
    assert mirelo.main(["preflight", "--video", str(video), "--out", str(tmp_path / "out")]) == 0
    data = json.loads(capsys.readouterr().out)
    cmd = shlex.split(data["next"].split(": ", 1)[1])
    assert cmd[2] == "preflight" and cmd[cmd.index("--prompt") + 1] == "<describe the sound>"


def test_cli_quote_next_is_optional_paid_command_without_approval_gate(tmp_path, monkeypatch, capsys):
    video = tmp_path / "silent.mp4"
    video.write_bytes(b"video")
    out = tmp_path / "out"
    monkeypatch.setattr(mirelo, "load_api_key", lambda: (KEY, "test"))
    monkeypatch.setattr(mirelo, "preflight", lambda *args: {"quoted_credits": 80})
    monkeypatch.setattr(mirelo, "generate", lambda *args: pytest.fail("cost-only preflight generated"))
    assert mirelo.main(["preflight", "--video", str(video), "--prompt", "two bounces", "--out", str(out)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["next"].startswith("Optional paid generation command: ")
    assert not any(word in data["next"].lower() for word in ("ask", "wait", "approv"))
    cmd = shlex.split(data["next"].split(": ", 1)[1])
    assert cmd[2] == "generate"
    assert cmd[cmd.index("--prompt") + 1] == "two bounces"
    assert cmd[cmd.index("--out") + 1] == str(out)


@pytest.mark.parametrize("source_change", ["replaced", "removed"])
def test_generate_uses_uploaded_snapshot_when_original_changes(run, source_change):
    sidecar = run.video.with_suffix(".json")
    sidecar.write_text('{"impacts":[2.0,5.0]}')
    http = FakeHTTP(create=(200, job_body("succeeded", url="https://dl/a.wav", credits=80)))
    run("preflight", http, prompt="two bounces")
    state = mirelo.load_state(run.out)
    snapshot = Path(state["snapshot"])
    assert snapshot.read_bytes() == b"video" and state["snapshot_sha256"] == mirelo.file_digest(snapshot)
    upload = next(r for r in http.requests if r[1] == "https://storage/up")
    assert b"video" in upload[3]
    if source_change == "replaced":
        run.video.write_bytes(b"replacement video")
        sidecar.write_text('{"impacts":[99]}')
    else:
        run.video.unlink()
        sidecar.unlink()

    def verify(video, out, saved):
        assert video == snapshot and video.read_bytes() == b"video"
        assert json.loads(video.with_suffix(".json").read_text()) == {"impacts": [2.0, 5.0]}
        return {"detected_onsets_s": [2.0, 5.0], "expected_impacts_s": [2.0, 5.0], "ok": True}

    res = run("generate", http, finish=verify)
    assert res["status"] == "done"
    count = len(http.requests)
    assert run("resume", http)["sync"] == res["sync"] == mirelo.load_state(run.out)["sync"]
    assert len(http.requests) == count


def test_resume_uses_snapshot_after_original_is_removed(run):
    http = FakeHTTP()
    assert run("generate", http)["status"] == "poll_timeout"
    run.video.unlink()
    http.polls = [job_body("succeeded", url="https://dl/a.wav", credits=80)]

    def verify(video, out, state):
        assert video == Path(state["snapshot"]) and video.read_bytes() == b"video"
        return {"detected_onsets_s": []}

    assert run("resume", http, finish=verify)["status"] == "done"


@pytest.mark.parametrize("target", ["video", "sidecar"])
def test_mutated_snapshot_blocks_pending_retry_without_remote_request(run, target):
    run.video.with_suffix(".json").write_text('{"impacts":[2.0]}')
    http = FakeHTTP(create=(503, {"error": {"message": "unavailable"}}))
    with pytest.raises(mirelo.MireloError):
        run("generate", http)
    state = mirelo.load_state(run.out)
    saved = Path(state["snapshot"])
    target_path = saved if target == "video" else saved.with_suffix(".json")
    target_path.chmod(0o600)
    target_path.write_bytes(b"changed")
    count = len(http.requests)
    with pytest.raises(mirelo.UsageError, match="saved.*changed"):
        run("generate", http)
    assert len(http.requests) == count and mirelo.load_state(run.out) == state


def test_failed_requote_preserves_prior_snapshot_and_quote(run):
    run("preflight", FakeHTTP(), prompt="two bounces")
    original = mirelo.load_state(run.out)
    run.video.write_bytes(b"replacement")
    with pytest.raises(mirelo.CreditCapError):
        run("preflight", FakeHTTP(credits=81), prompt="changed")
    assert mirelo.load_state(run.out) == original
    assert mirelo.saved_video(original).read_bytes() == b"video"


def test_installer_quotes_complete_paths_and_keeps_yaml_description_valid(tmp_path):
    clone = tmp_path / "clone with spaces 'single\"double"
    clone.mkdir()
    for filename in ("setup.sh", "SKILL.md", "mirelo.py"):
        shutil.copyfile(REPO / filename, clone / filename)
    skills = tmp_path / "isolated skills"
    env = {**os.environ, "OPENCLAW_SKILLS_DIR": str(skills)}
    output = subprocess.run(["bash", str(clone / "setup.sh")], env=env, text=True,
                            capture_output=True, check=True).stdout
    installed = (skills / "mirelo-sfx" / "SKILL.md").read_text()
    # JSON strings are valid YAML quoted scalars; decode the actual generated field.
    description = json.loads(installed.splitlines()[2].removeprefix("description: "))
    doctor = shlex.split(next(line.removeprefix("check: ") for line in output.splitlines()
                             if line.startswith("check: ")))
    assert doctor == ["python3", str(clone / "mirelo.py"), "doctor"]
    advertised = description.split("The only tool is `", 1)[1].split("`", 1)[0]
    assert shlex.split(advertised) == ["python3", str(clone / "mirelo.py")]
    for block in installed.split("```bash\n")[1:]:
        command = block.split("```", 1)[0].replace("\\\n", " ")
        args = shlex.split(command)
        assert args[0:2] == ["python3", str(clone / "mirelo.py")]
        if "--video" in args:
            assert args[args.index("--video") + 1] == str(clone / "examples" / "alien-shooter.mp4")
    # Execute the advertised program with a local-only --help command through Bash.
    smoke = subprocess.run(["bash", "-c", shlex.join(doctor[:2] + ["--help"])], text=True,
                           capture_output=True, check=True)
    assert "doctor,preflight,generate,resume" in smoke.stdout


# ---- status parsing

def test_parse_job_picks_first_succeeded_variant():
    data = {"id": "g", "status": "partially_succeeded", "credits": 80, "result": {"outputs": [{"variants": [
        {"status": "failed", "files": {"audio": {"url": "https://dl/bad"}}},
        {"status": "succeeded", "files": {"audio": {"url": "https://dl/good", "url_expires_at": "x"}}}]}]}}
    job = mirelo.parse_job(data)
    assert job["download_url"] == "https://dl/good" and job["credits"] == 80


def test_unknown_status_keeps_polling_and_failed_reports_errors(run):
    http = FakeHTTP(polls=[job_body("warming_up"), job_body("failed", credits=0,
                                                            errors=[{"code": "generation_failed", "message": "boom"}])])
    res = run("generate", http)
    assert res["status"] == "failed" and "generation_failed" in res["message"]
    assert http.count("GET", "/generations/gen_1") == 2


# ---- download URL refresh

def test_expired_download_refreshes_once(run):
    http = FakeHTTP(create=(200, job_body("succeeded", url="https://dl/old.wav")),
                    polls=[job_body("succeeded", url="https://dl/new.wav")], downloads=["expired"])
    assert run("generate", http)["status"] == "done"
    assert http.count("GET", "https://dl/") == 2 and http.count("GET", "/generations/gen_1") == 1


def test_second_expiry_surfaces_and_resume_recovers(run):
    http = FakeHTTP(create=(200, job_body("succeeded", url="https://dl/old.wav")),
                    polls=[job_body("succeeded", url="https://dl/new.wav")], downloads=["expired", "expired"])
    with pytest.raises(mirelo.DownloadExpired):
        run("generate", http)
    assert run("resume", http)["status"] == "done"
    assert http.count("POST", "/generations?wait") == 1


# ---- media

def clicks_wav(path, clicks, duration=8.0, rate=48000):
    frames = bytearray()
    starts = {int(c * rate) for c in clicks}
    start, until = 0, -1
    for i in range(int(duration * rate)):
        if i in starts:
            start, until = i, i + int(0.06 * rate)
        k = i - start
        v = int(20000 * math.exp(-k / (0.015 * rate)) * math.sin(2 * math.pi * 800 * k / rate)) if i < until else 0
        frames += struct.pack("<h", v)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return path


@needs_ffmpeg
@pytest.mark.parametrize("filename", ["silent.mp4", "artemis-liftoff.mp4", "alien-shooter.mp4"])
def test_example_clip_is_silent_8s_720p30(filename):
    clip = REPO / "examples" / filename
    streams = mirelo.ffprobe(clip, "-show_streams")["streams"]
    assert [s["codec_type"] for s in streams] == ["video"]
    assert (streams[0]["width"], streams[0]["height"], streams[0]["r_frame_rate"]) == (1280, 720, "30/1")
    assert mirelo.duration_ms_for(mirelo.duration_s(clip)) == 8000


@needs_ffmpeg
def test_generate_muxes_outputs_and_checks_sync(tmp_path):
    video = tmp_path / "clip" / "silent.mp4"
    video.parent.mkdir()
    shutil.copy(REPO / "examples" / "silent.mp4", video)
    shutil.copy(REPO / "examples" / "silent.json", video.with_suffix(".json"))
    wav = clicks_wav(tmp_path / "gen.wav", [2.0, 5.0]).read_bytes()
    http = FakeHTTP(create=(200, job_body("succeeded", url="https://dl/a.wav", credits=80)), wav=wav)
    out = tmp_path / "runs" / "1"
    res = mirelo.generate(video, "two bounces", out, mirelo.Client(KEY, http))
    assert res["status"] == "done" and res["sync"]["ok"] is True
    assert set(res["sync"]) == {"detected_onsets_s", "expected_impacts_s", "ok"}
    assert res["sync"]["expected_impacts_s"] == [2.0, 5.0]
    assert res["sync"]["detected_onsets_s"] == pytest.approx([2.0, 5.0], abs=0.1)
    notes = (out / "player.html").read_text()
    assert "detected sound onsets (s)" in notes and "expected impacts (s): [2.0, 5.0]" in notes
    for name in ("silent.mp4", "sound.wav", "with-sound.mp4", "player.html", "job.json"):
        assert (out / name).is_file()
    kinds = sorted(s["codec_type"] for s in mirelo.ffprobe(out / "with-sound.mp4", "-show_streams")["streams"])
    assert kinds == ["audio", "video"]
    assert "gen_1" in (out / "player.html").read_text()
    assert KEY not in (out / "job.json").read_text()
    assert mirelo.resume(out, mirelo.Client(KEY, http))["sync"] == res["sync"]
