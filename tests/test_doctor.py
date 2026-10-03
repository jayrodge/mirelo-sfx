import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('mirelo_doctor_test', Path(__file__).parents[1] / 'mirelo.py')
mirelo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirelo)


def test_doctor_reports_both_agents_and_honors_installer_destinations(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    oc, hermes = tmp_path / 'oc-state', tmp_path / 'hermes-profile'
    monkeypatch.setenv('OPENCLAW_SKILLS_DIR', str(oc / 'skills'))
    monkeypatch.setenv('HERMES_SKILLS_DIR', str(hermes / 'skills'))
    monkeypatch.setenv('HERMES_HOME', str(tmp_path / 'stale-home'))
    for root in (oc, hermes):
        skill = root / 'skills/mirelo-sfx/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('skill')
    monkeypatch.setattr(mirelo, 'load_api_key', lambda: ('test', 'test env'))
    monkeypatch.setattr(mirelo.Client, 'me', lambda self: {'credits_available': 500})
    monkeypatch.setattr(mirelo.shutil, 'which', lambda name: '/test/' + name)
    result, ok = mirelo.doctor()
    assert ok
    assert result['skills'] == {name: str(root / 'skills/mirelo-sfx/SKILL.md')
                                for name, root in [('openclaw', oc), ('hermes', hermes)]}
    assert result['skill'] == result['skills']['openclaw']


def test_doctor_native_hermes_matches_setup_with_stale_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('HERMES_HOME', str(tmp_path / 'stale'))
    monkeypatch.delenv('HERMES_SKILLS_DIR', raising=False)
    skill = tmp_path / '.hermes/skills/mirelo-sfx/SKILL.md'
    skill.parent.mkdir(parents=True)
    skill.write_text('skill')
    monkeypatch.setattr(mirelo, 'load_api_key', lambda: ('test', 'test env'))
    monkeypatch.setattr(mirelo.Client, 'me', lambda self: {})
    result, _ = mirelo.doctor()
    assert result['skills']['hermes'] == str(skill)
