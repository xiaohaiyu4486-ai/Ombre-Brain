from unittest.mock import MagicMock

import pytest

import tools._runtime as rt
from tools.trace.core import trace_core


class StaticAnalyzer:
    def __init__(self, result=None, error=None):
        self.result = result or {
            "domain": ["健康", "待办"],
            "tags": ["复查", "重要"],
            "valence": 0.2,
            "arousal": 0.8,
            "importance": 9,
            "suggested_name": "模型不得覆盖现有标题",
        }
        self.error = error
        self.calls = []

    async def analyze(self, content):
        self.calls.append(content)
        if self.error is not None:
            raise self.error
        return self.result


def install_runtime(bucket_mgr, analyzer):
    rt.config = {"surfacing": {}}
    rt.bucket_mgr = bucket_mgr
    rt.dehydrator = analyzer
    rt.logger = MagicMock()
    rt.fire_webhook = None
    rt.mark_op = None


@pytest.mark.asyncio
async def test_trace_reclassify_updates_only_derived_metadata(bucket_mgr):
    bucket_id = await bucket_mgr.create(
        content="下周复查，结果必须记得跟进。",
        name="原始标题",
        importance=5,
        domain=["未分类"],
        valence=0.5,
        arousal=0.3,
    )
    analyzer = StaticAnalyzer()
    install_runtime(bucket_mgr, analyzer)

    before = await bucket_mgr.get(bucket_id)
    result = await trace_core(bucket_id, reclassify=True)
    after = await bucket_mgr.get(bucket_id)

    assert analyzer.calls == [before["content"]]
    assert "正文与标题未修改" in result
    assert after["content"] == before["content"]
    assert after["metadata"]["name"] == before["metadata"]["name"]
    assert after["metadata"]["domain"] == ["健康", "待办"]
    assert after["metadata"]["tags"] == ["复查", "重要"]
    assert after["metadata"]["valence"] == 0.2
    assert after["metadata"]["arousal"] == 0.8
    assert after["metadata"]["importance"] == 9


@pytest.mark.asyncio
async def test_trace_reclassify_preserves_guarded_importance(bucket_mgr):
    bucket_id = await bucket_mgr.create(
        content="这是永久核心规则。",
        name="不可降级",
        importance=10,
        pinned=True,
        domain=["家规"],
    )
    analyzer = StaticAnalyzer(result={
        "domain": ["家规"],
        "tags": ["核心"],
        "valence": 0.7,
        "arousal": 0.6,
        "importance": 3,
    })
    install_runtime(bucket_mgr, analyzer)

    result = await trace_core(bucket_id, reclassify=True)
    after = await bucket_mgr.get(bucket_id)

    assert "importance=10" in result
    assert after["metadata"]["pinned"] is True
    assert after["metadata"]["importance"] == 10


@pytest.mark.asyncio
async def test_trace_reclassify_failure_and_conflict_are_noops(bucket_mgr):
    bucket_id = await bucket_mgr.create(
        content="这条记忆不能被失败的重打标破坏。",
        name="保持原样",
        importance=5,
        domain=["未分类"],
    )
    analyzer = StaticAnalyzer(error=RuntimeError("secret provider detail"))
    install_runtime(bucket_mgr, analyzer)
    before = await bucket_mgr.get(bucket_id)

    failed = await trace_core(bucket_id, reclassify=True)
    after_failed = await bucket_mgr.get(bucket_id)
    conflicted = await trace_core(bucket_id, reclassify=True, importance=8)
    after_conflict = await bucket_mgr.get(bucket_id)

    assert "secret provider detail" not in failed
    assert "均未修改" in failed
    assert "必须单独调用" in conflicted
    assert analyzer.calls == [before["content"]]
    assert after_failed == before
    assert after_conflict == before
