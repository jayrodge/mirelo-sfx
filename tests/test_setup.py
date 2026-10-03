"""Installer boundaries: destination selection and safe command rendering."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def install_env(tmp_path):
    clone = tmp_path / "clone with 'quotes'"
    clone.mkdir()
    for name in ("setup.sh", "SKILL.md", "mirelo.py"):
        shutil.copy2(REPO / name, clone / name)
    home = tmp_path / "home"
    home.mkdir()
    bins = tmp_path / "bin"
    bins.mkdir()
    (bins / "python3").symlink_to(sys.executable)
    for name in ("ffmpeg", "ffprobe"):
        tool = bins / name
        tool.write_text("#!/bin/sh\nexit 0\n")
        tool.chmod(0o755)
    env = os.environ.copy()
    for key in ("OPENCLAW_SKILLS_DIR", "HERMES_SKILLS_DIR", "MIRELO_API_KEY"):
        env.pop(key, None)
    env.update(HOME=str(home), PATH=str(bins) + os.pathsep + env["PATH"],
               HERMES_HOME=str(tmp_path / "obsolete-runtime"))
    return clone, home, env


def install(clone, env, *args):
    return subprocess.run(["bash", str(clone / "setup.sh"), *args], env=env,
                          capture_output=True, text=True)


@pytest.mark.parametrize("args,agent", [((), "openclaw"),
                                        (("--agent", "openclaw"), "openclaw"),
                                        (("--agent", "hermes"), "hermes")])
def test_native_agent_destination_and_rendering(install_env, args, agent):
    clone, home, env = install_env
    config = home / f".{agent}" / "config.yaml"
    config.parent.mkdir()
    config.write_text("model: leave-me-alone\n")
    result = install(clone, env, *args)
    assert result.returncode == 0, result.stderr
    skill = config.parent / "skills/mirelo-sfx/SKILL.md"
    text = skill.read_text()
    description = json.loads(text.splitlines()[2].removeprefix("description: "))
    assert "name: mirelo-sfx" in text
    assert "~/mirelo-sfx/" not in text
    # Quoted clone paths remain valid shell arguments, including spaces/apostrophes.
    import shlex
    assert description == json.loads((clone / "SKILL.md").read_text().splitlines()[2].removeprefix("description: "))
    assert shlex.quote(str(clone / "mirelo.py")) in text
    assert shlex.quote(str(clone / "examples/alien-shooter.mp4")) in text
    assert config.read_text() == "model: leave-me-alone\n"
    assert not Path(env["HERMES_HOME"]).exists()
    other = "hermes" if agent == "openclaw" else "openclaw"
    assert not (home / f".{other}" / "skills").exists()


@pytest.mark.parametrize("agent,variable", [("openclaw", "OPENCLAW_SKILLS_DIR"),
                                            ("hermes", "HERMES_SKILLS_DIR")])
def test_selected_agent_custom_destination(install_env, tmp_path, agent, variable):
    clone, home, env = install_env
    dest = tmp_path / "custom skills"
    env[variable] = str(dest)
    env["HERMES_SKILLS_DIR" if agent == "openclaw" else "OPENCLAW_SKILLS_DIR"] = str(tmp_path / "wrong")
    result = install(clone, env, "--agent", agent)
    assert result.returncode == 0, result.stderr
    assert (dest / "mirelo-sfx/SKILL.md").is_file()
    assert not (tmp_path / "wrong").exists()


@pytest.mark.parametrize("args", [("--agent", "unknown"), ("--agent",),
                                  ("--invalid",), ("--agent", "hermes", "extra")])
def test_invalid_arguments_write_nothing(install_env, args):
    clone, home, env = install_env
    result = install(clone, env, *args)
    assert result.returncode == 2
    assert not list(home.iterdir())


def test_help_writes_nothing(install_env):
    clone, home, env = install_env
    result = install(clone, env, "--help")
    assert result.returncode == 0
    assert "openclaw|hermes" in result.stdout
    assert not list(home.iterdir())
