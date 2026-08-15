from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_API = ROOT / "src" / "web" / "config_api.py"


def test_dehydration_probe_exercises_live_structured_tagging_path():
    source = CONFIG_API.read_text(encoding="utf-8")
    start = source.index("async def api_test_dehydration(")
    end = source.index("# /api/test/embedding", start)
    probe = source[start:end]

    assert "dehyd = sh.dehydrator" in probe
    assert "analysis = await dehyd.analyze(" in probe
    assert 'analysis.get("tags") or analysis.get("suggested_name")' in probe
    assert '"content": "hi"' not in probe
