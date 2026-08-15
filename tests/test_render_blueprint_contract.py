from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "frontend" / "dashboard.html"


def test_render_blueprint_uses_paid_plan_and_persistent_config_path():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    service = blueprint["services"][0]
    env = {item["key"]: item for item in service["envVars"]}

    assert service["plan"] == "starter"
    assert service["disk"]["mountPath"] == env["OMBRE_BUCKETS_DIR"]["value"]
    assert env["OMBRE_CONFIG_PATH"]["value"].startswith(
        service["disk"]["mountPath"] + "/"
    )


def test_claude_blueprint_is_isolated_manual_and_provider_safe():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    service = blueprint["services"][0]
    env = {item["key"]: item for item in service["envVars"]}

    assert service["name"] == "ombre-brain-claude"
    assert service["branch"] == "codex/claude-upgrade"
    assert service["autoDeployTrigger"] == "off"
    assert service["disk"]["name"] == "ombre-claude-data"
    assert service["disk"]["sizeGB"] == 1
    assert env["OMBRE_PUBLIC_URL"]["value"] == (
        "https://ombre-brain-claude.onrender.com"
    )
    assert env["OMBRE_OWNER_NAME"]["value"] == "Claude"
    assert env["OMBRE_BREATH_RECENT_FIRST"]["value"] == "true"
    assert env["OMBRE_COMPRESS_MODEL"]["value"] == "deepseek-ai/DeepSeek-V3.2"
    assert env["OMBRE_EMBED_MODEL"]["value"] == "BAAI/bge-m3"
    assert env["OMBRE_COMPRESS_BASE_URL"]["value"] == (
        "https://api.siliconflow.cn/v1"
    )
    assert env["OMBRE_EMBED_BASE_URL"]["value"] == (
        "https://api.siliconflow.cn/v1"
    )
    assert "OMBRE_COMPRESS_API_KEY" not in env
    assert "OMBRE_EMBED_API_KEY" not in env


def test_dashboard_warns_that_render_hot_update_will_roll_back():
    html = DASHBOARD.read_text(encoding="utf-8")

    assert "if (_deployInfo && _deployInfo.is_render)" in html
    assert "平台重启或重新部署后会回滚" in html
    assert "建议取消并改用 Render 正式部署" in html
