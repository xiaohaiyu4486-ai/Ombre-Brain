# ============================================================
# Test: 7/11 OB 改造清单 — 冷却/用进废退/统一候选池/近重合并/情绪门控
# Ticket 272bd9ea9e74 items #1/#2/#8 — pure local, no LLM needed
# ============================================================

import pytest
import pytest_asyncio
import frontmatter as fm
from datetime import datetime, timedelta

from bucket_manager import BucketManager


# ============================================================
# 工单#1: mark_surfaced (用进废退) + surfacing cooldown (检索冷却)
# ============================================================

@pytest.mark.asyncio
async def test_mark_surfaced_bookkeeping(bucket_mgr):
    """mark_surfaced 应加 surface_count/last_surfaced/activation_count，不动 last_active。"""
    bid = await bucket_mgr.create(content="测试记忆内容", importance=5)
    before = await bucket_mgr.get(bid)
    last_active_before = before["metadata"]["last_active"]

    await bucket_mgr.mark_surfaced(bid)
    after = await bucket_mgr.get(bid)
    meta = after["metadata"]

    assert meta["surface_count"] == 1
    assert meta.get("last_surfaced")
    assert abs(float(meta["activation_count"]) - 0.2) < 1e-6
    # 不重置衰减计时
    assert meta["last_active"] == last_active_before

    await bucket_mgr.mark_surfaced(bid)
    meta2 = (await bucket_mgr.get(bid))["metadata"]
    assert meta2["surface_count"] == 2
    assert abs(float(meta2["activation_count"]) - 0.4) < 1e-6


def _meta(last_surfaced_min_ago=None, surface_count=0, pinned=False):
    meta = {"surface_count": surface_count}
    if pinned:
        meta["pinned"] = True
    if last_surfaced_min_ago is not None:
        meta["last_surfaced"] = (
            datetime.now() - timedelta(minutes=last_surfaced_min_ago)
        ).isoformat()
    return meta


def test_cooldown_never_surfaced():
    assert not BucketManager.surfacing_cooldown_active(_meta())


def test_cooldown_just_surfaced():
    assert BucketManager.surfacing_cooldown_active(_meta(last_surfaced_min_ago=5))


def test_cooldown_expired_base_window():
    # 基础冷却 30 分钟：31 分钟前浮现过 → 不再冷却
    assert not BucketManager.surfacing_cooldown_active(
        _meta(last_surfaced_min_ago=31, surface_count=1)
    )


def test_cooldown_grows_with_surface_count():
    # surface_count=10 → 冷却 30+30*2=90 分钟：60 分钟前浮现过 → 仍在冷却
    assert BucketManager.surfacing_cooldown_active(
        _meta(last_surfaced_min_ago=60, surface_count=10)
    )


def test_cooldown_capped_at_3h():
    # surface_count=100 → 上限 180 分钟：181 分钟前 → 不冷却
    assert not BucketManager.surfacing_cooldown_active(
        _meta(last_surfaced_min_ago=181, surface_count=100)
    )


def test_cooldown_pinned_exempt():
    assert not BucketManager.surfacing_cooldown_active(
        _meta(last_surfaced_min_ago=1, surface_count=50, pinned=True)
    )


# ============================================================
# 工单#8: score_for_query 统一评分（向量通道同分制）
# ============================================================

@pytest.mark.asyncio
async def test_topic_override_lifts_vector_match(bucket_mgr):
    """字面不沾边但语义相似度高的桶，经 topic_override 应得到更高统一分。"""
    bid = await bucket_mgr.create(content="今天去了海边看日落", importance=5)
    bucket = await bucket_mgr.get(bid)

    plain = bucket_mgr.score_for_query(
        "量子力学作业", bucket, enforce_threshold=False
    )
    lifted = bucket_mgr.score_for_query(
        "量子力学作业", bucket, topic_override=0.9, enforce_threshold=False
    )
    assert lifted > plain


@pytest.mark.asyncio
async def test_enforce_threshold_off_returns_score(bucket_mgr):
    """enforce_threshold=False 时低于阈值也返回分数（向量通道有自己的门槛）。"""
    bid = await bucket_mgr.create(content="完全无关的内容甲乙丙", importance=1)
    bucket = await bucket_mgr.get(bid)

    gated = bucket_mgr.score_for_query("毫无交集的检索词", bucket)
    ungated = bucket_mgr.score_for_query(
        "毫无交集的检索词", bucket, enforce_threshold=False
    )
    if gated is None:  # 确实低于阈值时，关闸后仍应有分数
        assert ungated is not None and ungated >= 0


# ============================================================
# 工单#2: 情绪温度门控 + 近重合并
# ============================================================

@pytest.mark.asyncio
async def test_hot_memory_gated_in_calm_context(bucket_mgr):
    """高唤醒记忆在平静语境（无/低 query arousal）下应被降权。"""
    hot_id = await bucket_mgr.create(
        content="共同主题词的记忆内容", importance=5, arousal=0.9, valence=0.5
    )
    calm_id = await bucket_mgr.create(
        content="共同主题词的记忆内容", importance=5, arousal=0.3, valence=0.5
    )
    hot = await bucket_mgr.get(hot_id)
    calm = await bucket_mgr.get(calm_id)

    hot_score = bucket_mgr.score_for_query(
        "共同主题词", hot, enforce_threshold=False
    )
    calm_score = bucket_mgr.score_for_query(
        "共同主题词", calm, enforce_threshold=False
    )
    assert hot_score < calm_score

    # 高唤醒语境下不再门控（emotion resonance 反而加分）
    hot_score_hot_ctx = bucket_mgr.score_for_query(
        "共同主题词", hot, query_arousal=0.9, query_valence=0.5,
        enforce_threshold=False,
    )
    assert hot_score_hot_ctx > hot_score


def _fake_bucket(bid, content, created, score):
    return {
        "id": bid,
        "content": content,
        "score": score,
        "metadata": {"created": created.isoformat()},
    }


def test_dedupe_same_hour_near_identical():
    now = datetime.now()
    b1 = _fake_bucket("a", "今天买了草莓蛋糕很好吃", now, 90)
    b2 = _fake_bucket("b", "今天买了草莓蛋糕很好吃！", now + timedelta(minutes=10), 80)
    kept = BucketManager.dedupe_near_duplicates([b1, b2])
    assert [b["id"] for b in kept] == ["a"]  # 留分高的


def test_dedupe_keeps_different_content():
    now = datetime.now()
    b1 = _fake_bucket("a", "今天买了草莓蛋糕很好吃", now, 90)
    b2 = _fake_bucket("b", "古汉语考试重点是通假字和虚词", now, 80)
    kept = BucketManager.dedupe_near_duplicates([b1, b2])
    assert len(kept) == 2


def test_dedupe_keeps_same_content_far_apart_in_time():
    now = datetime.now()
    b1 = _fake_bucket("a", "今天买了草莓蛋糕很好吃", now, 90)
    b2 = _fake_bucket("b", "今天买了草莓蛋糕很好吃", now - timedelta(days=3), 80)
    kept = BucketManager.dedupe_near_duplicates([b1, b2])
    assert len(kept) == 2  # 相隔3天的相似记忆是重复经历，不是重复记录
