"""
Brain 模块独立演示（无外部依赖）

运行方式:
    python examples/brain_demo_standalone.py

演示内容:
    1. 预测-学习循环：Agent 执行任务前预测结果，执行后学习
    2. 有限工作记忆：信息超出容量时自动压缩
    3. 记忆整合（"睡眠"）：定期整理经验，发现规律
"""

import sys
import os

# 使 import 能找到 agent 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 需要 mock 掉依赖 (observability 模块)
# 创建一个 mock 来绕过 langchain 等依赖

import types
import logging

# Mock agent.observability
observability_mock = types.ModuleType("agent.observability")

def _get_logger(name):
    return logging.getLogger(name)

class _MockSpan:
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def set_attribute(self, *a): pass
    def set_status(self, *a): pass

class _MockTracer:
    def start_span(self, name):
        return _MockSpan()
    def trace(self, name):
        def decorator(func):
            return func
        return decorator

def _get_tracer(name):
    return _MockTracer()

def _set_trace_context(**kw):
    pass

observability_mock.get_logger = _get_logger
observability_mock.get_tracer = _get_tracer
observability_mock.set_trace_context = _set_trace_context
sys.modules["agent.observability"] = observability_mock

# 现在可以安全 import brain 模块了
from agent.brain.predictor import PredictiveLoop, Prediction
from agent.brain.working_memory import WorkingMemory
from agent.brain.consolidation import MemoryConsolidation


def demo_prediction_loop():
    """演示 1：预测-学习循环"""
    print("=" * 60)
    print("  演示 1：预测-学习循环")
    print("  大脑通过预测错误来学习（Predictive Coding）")
    print("=" * 60)
    print()

    loop = PredictiveLoop(storage_path="/tmp/brain_demo/world_model.json")

    # 模拟 Agent 执行一系列任务
    tasks = [
        ("run_tests", {"file": "auth.py"}, "fail: 2 errors"),
        ("edit_file", {"file": "auth.py"}, "success: file saved"),
        ("run_tests", {"file": "auth.py"}, "pass: all green"),
        ("run_tests", {"file": "auth.py"}, "pass: all green"),
        ("run_tests", {"file": "auth.py"}, "pass: all green"),
        ("run_tests", {"file": "payment.py"}, "fail: timeout"),
        ("edit_file", {"file": "payment.py"}, "success: file saved"),
        ("run_tests", {"file": "payment.py"}, "fail: still timeout"),
        ("run_tests", {"file": "payment.py"}, "pass: fixed"),
        ("deploy", {"target": "staging"}, "success: deployed"),
        ("deploy", {"target": "staging"}, "success: deployed"),
        ("deploy", {"target": "production"}, "fail: health check failed"),
    ]

    print("Agent 开始执行任务序列...\n")

    for i, (action, context, actual) in enumerate(tasks, 1):
        # 1. 预测
        prediction = loop.predict(action, context)
        
        # 2. 学习
        error = loop.learn(action, context, prediction, actual)
        
        # 3. 展示
        pred_str = prediction.predicted_outcome[:30]
        actual_str = actual[:30]
        
        if error.magnitude < 0.3:
            status = "✓ 预测正确"
        elif error.surprise == "high":
            status = "‼ 非常惊讶"
        else:
            status = "✗ 预测错误"
        
        print(f"  [{i:2d}] {action:<12} | 预测: {pred_str:<20} | 实际: {actual_str:<20} | {status}")

    # 显示学习结果
    print(f"\n  ─── 学习结果 ───")
    print(f"  预测准确率: {loop.get_accuracy():.0%}")
    print(f"  世界模型规律数: {len(loop._world_model)}")
    print()
    print(f"  {loop.get_world_model_summary()}")


def demo_working_memory():
    """演示 2：有限工作记忆"""
    print("\n\n")
    print("=" * 60)
    print("  演示 2：有限工作记忆（容量 = 5）")
    print("  容量满了必须压缩 → 逼出抽象能力")
    print("=" * 60)
    print()

    wm = WorkingMemory(capacity=5)

    # 模拟信息流
    info_stream = [
        ("用户要求: 重构 UserService 类", 0.9, "task"),
        ("UserService.py 有 500 行代码", 0.5, "context"),
        ("依赖: DatabasePool, CacheManager, Logger", 0.6, "context"),
        ("当前有 3 个 public 方法和 12 个 private 方法", 0.4, "context"),
        ("用户说: 拆分成 UserAuth 和 UserProfile", 0.8, "task"),
        ("发现: UserService 被 PaymentService 引用", 0.7, "context"),
        ("注意: 修改后需要更新 20 个测试文件", 0.6, "context"),
        ("insight: 先用接口抽象，再做拆分", 0.8, "insight"),
    ]

    print("信息依次进入工作记忆...\n")

    for content, importance, category in info_stream:
        compressed = wm.push(content, importance, category)
        usage = f"[{wm.size}/{wm.capacity}]"
        
        if compressed:
            print(f"  {usage} 输入: {content[:45]}")
            print(f"         → 💡 压缩触发! 生成: '{compressed.content}'")
        else:
            print(f"  {usage} 输入: {content[:45]}")
    
    print(f"\n  ─── 最终状态 ───")
    print(f"  {wm.get_summary()}")

    # 测试回忆
    print(f"\n  尝试回忆 'Database':")
    recalled = wm.recall_from_archive("Database")
    for chunk in recalled:
        print(f"    回忆到: {chunk.content}")
    if not recalled:
        results = wm.search("Database")
        for chunk in results:
            print(f"    工作记忆中找到: {chunk.content}")


def demo_consolidation():
    """演示 3：记忆整合（"睡眠"）"""
    print("\n\n")
    print("=" * 60)
    print("  演示 3：记忆整合（Agent 的'睡眠'）")
    print("  定期整理经验，自动发现隐藏规律")
    print("=" * 60)
    print()

    mc = MemoryConsolidation(storage_path="/tmp/brain_demo/consolidation.json")

    # 模拟大量经验积累
    experiences = [
        # auth.py 总是出问题
        ("run_tests", {"file": "auth.py"}, "fail: null pointer", 0.7, -0.5),
        ("edit_file", {"file": "auth.py"}, "success", 0.5, 0.1),
        ("run_tests", {"file": "auth.py"}, "fail: type error", 0.7, -0.5),
        ("edit_file", {"file": "auth.py"}, "success", 0.5, 0.1),
        ("run_tests", {"file": "auth.py"}, "fail: assertion", 0.7, -0.5),
        ("run_tests", {"file": "auth.py"}, "pass", 0.4, 0.3),
        
        # payment.py 改完总要 deploy
        ("edit_file", {"file": "payment.py"}, "success", 0.5, 0.1),
        ("run_tests", {"file": "payment.py"}, "pass", 0.4, 0.2),
        ("deploy", {"target": "staging"}, "success", 0.6, 0.3),
        
        ("edit_file", {"file": "payment.py"}, "success", 0.5, 0.1),
        ("run_tests", {"file": "payment.py"}, "pass", 0.4, 0.2),
        ("deploy", {"target": "staging"}, "success", 0.6, 0.3),

        ("edit_file", {"file": "payment.py"}, "success", 0.5, 0.1),
        ("run_tests", {"file": "payment.py"}, "pass", 0.4, 0.2),
        ("deploy", {"target": "staging"}, "fail: config error", 0.8, -0.7),

        # utils.py 很稳定
        ("edit_file", {"file": "utils.py"}, "success", 0.3, 0.1),
        ("run_tests", {"file": "utils.py"}, "pass", 0.3, 0.1),
        ("edit_file", {"file": "utils.py"}, "success", 0.3, 0.1),
        ("run_tests", {"file": "utils.py"}, "pass", 0.3, 0.1),
        ("edit_file", {"file": "utils.py"}, "success", 0.3, 0.1),
        ("run_tests", {"file": "utils.py"}, "pass", 0.3, 0.1),
    ]

    print(f"  积累经验中... ({len(experiences)} 条)\n")
    for action, context, outcome, importance, valence in experiences:
        mc.record_experience(
            action=action,
            context=context,
            outcome=outcome,
            importance=importance,
            emotional_valence=valence,
        )

    # 触发整合！
    print("  💤 触发'睡眠'整合...\n")
    insights = mc.consolidate()

    print(f"  发现 {len(insights)} 条洞察:\n")
    for i, insight in enumerate(insights, 1):
        emoji = "🔴" if insight.category == "warning" else "🔵" if insight.category == "pattern" else "🟡" if insight.category == "rule" else "🟢"
        print(f"    {emoji} [{insight.category}] {insight.pattern}")
        print(f"       置信度: {insight.confidence:.0%}, 证据: {insight.evidence_count} 条")
        print()

    # 尝试获取建议
    print("  ─── 针对 'run_tests auth.py' 的建议 ───")
    relevant = mc.get_relevant_insights("run_tests", {"file": "auth.py"})
    for ins in relevant:
        print(f"    ⚡ {ins.pattern}")

    print(f"\n  {mc.get_summary()}")


def demo_integrated():
    """演示 4：三模块协同工作"""
    print("\n\n")
    print("=" * 60)
    print("  演示 4：三模块协同 — Agent 大脑完整运作")
    print("=" * 60)
    print()

    # 初始化
    predictor = PredictiveLoop(storage_path="/tmp/brain_demo/integrated_wm.json")
    wm = WorkingMemory(capacity=5)
    mc = MemoryConsolidation(storage_path="/tmp/brain_demo/integrated_cons.json")

    # 模拟一个完整工作场景
    print("  场景：Agent 接到任务修复 bug\n")

    # Step 1: 接收任务 → 推入工作记忆
    print("  [Step 1] 接收任务")
    wm.push("修复 user_service.py 的空指针错误", importance=0.9, category="task")
    wm.push("错误: NoneType has no attr 'email'", importance=0.7, category="context")
    wm.push("影响: 约 10% 的请求失败", importance=0.6, category="context")
    print(f"    工作记忆: {[c.content[:30] for c in wm.get_focus()]}")
    print()

    # Step 2: 查询历史经验
    print("  [Step 2] 查询历史经验")
    insights = mc.get_relevant_insights("edit_file", {"file": "user_service.py"})
    if insights:
        print(f"    历史建议: {insights[0].pattern}")
    else:
        print(f"    (无历史经验，首次操作)")
    print()

    # Step 3: 预测结果
    print("  [Step 3] 预测修复结果")
    pred = predictor.predict("edit_file", {"file": "user_service.py", "change": "add null check"})
    print(f"    预测: {pred.predicted_outcome} (信心 {pred.confidence:.0%})")
    print(f"    依据: {pred.reasoning}")
    print()

    # Step 4: 执行并学习
    print("  [Step 4] 执行修复 → 成功!")
    actual = "success: null check added, tests pass"
    error = predictor.learn("edit_file", {"file": "user_service.py", "change": "add null check"}, pred, actual)
    mc.record_experience("edit_file", {"file": "user_service.py"}, actual, importance=0.7, emotional_valence=0.5)
    print(f"    学习: 误差={error.magnitude:.2f}, {error.lesson[:50]}")
    
    # 推入结果到工作记忆
    wm.push(f"修复成功: {actual[:40]}", importance=0.6, category="result")
    print()

    # Step 5: 展示最终状态
    print("  [Step 5] 当前大脑状态")
    print(f"    工作记忆: {wm.size}/{wm.capacity} slots")
    print(f"    聚焦: {[c.content[:25] + '...' for c in wm.get_focus(top_n=3)]}")
    print(f"    世界模型: {len(predictor._world_model)} 条规律")
    print(f"    经验库: {len(mc._experiences)} 条经验")


if __name__ == "__main__":
    # 清理之前的数据
    import shutil
    if os.path.exists("/tmp/brain_demo"):
        shutil.rmtree("/tmp/brain_demo")
    os.makedirs("/tmp/brain_demo", exist_ok=True)

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        🧠 Brain Module Demo — 类脑认知系统演示               ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    demo_prediction_loop()
    demo_working_memory()
    demo_consolidation()
    demo_integrated()

    print("\n")
    print("═" * 60)
    print("  ✅ 演示完成！")
    print()
    print("  这三个模块让 Agent 具备了：")
    print("    1. 预测-学习循环 → 从错误中成长，不再重蹈覆辙")
    print("    2. 有限工作记忆   → 强制抽象，聚焦核心")
    print("    3. 记忆整合       → 睡一觉发现规律，越用越聪明")
    print()
    print("  下一步：将 Brain 接入 Agent 主循环！")
    print("═" * 60)
