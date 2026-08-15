# Claude vault upgrade compatibility matrix

This branch upgrades the isolated Claude vault from the legacy fork to upstream
2.17.9 without copying old implementation files. Each legacy behavior was
checked independently and only missing semantics received a narrow patch.

| Legacy requirement | Upstream 2.17.9 finding | Branch decision | Regression evidence |
|---|---|---|---|
| Provider failure must not lose `hold` body | Already stores the complete body with local neutral metadata; raw merge preserves source text | Keep upstream behavior; hide provider exception details in fallback logs | `tests/test_source_layer.py`, `tests/test_breath_verbatim_patch.py` |
| Digest/tagging failure must not refuse `grow` | Long digest and short tagging paths still raised before storage | Fall back to one verbatim bucket with neutral metadata; never copy provider text into responses/logs | `tests/test_grow_items.py` |
| Pinned rules must not starve newest memories | Default mode skips ordinary surfacing whenever any core rule is omitted | Add opt-in `OMBRE_BREATH_RECENT_FIRST=true`; newest-first full-text recall gets an independent 6000-token floor and always returns at least the newest eligible bucket | `tests/test_breath_verbatim_patch.py`, `tests/test_env_config_identity.py` |
| Dehydration must not overwrite returned/stored body | Current breath rendering reads stored content directly and does not call the LLM; hold/items use raw merge | Keep upstream implementation | `tests/test_breath_verbatim_patch.py` |
| Provider setup must not create a mixed runtime tuple or a false-green probe | Quick compression save only sent the key; probe used a tiny raw request | Save key/base/model/format atomically and test the live structured tagging path | `tests/test_dashboard_env_config_contract.py`, `tests/test_dehydration_probe_contract.py`, `tests/test_phase2_web_security.py` |

Deployment invariants for this branch:

- Service: `ombre-brain-claude`; disk: `ombre-claude-data`; branch:
  `codex/claude-upgrade`; automatic deploy disabled.
- `OMBRE_BUCKETS_DIR` and `OMBRE_CONFIG_PATH` point only to the new disk.
- Compression is pinned to `Qwen/Qwen2.5-7B-Instruct` through SiliconFlow.
- Embedding is pinned to `BAAI/bge-m3` through SiliconFlow. Changing it requires
  a complete atomic re-vectorization; old `embeddings.db` is never imported.
- Provider keys are intentionally absent from `render.yaml` and must be set as
  Render environment secrets after the empty service is healthy.
