"""
Brain 模块使用演示

运行方式:
    cd /projects/sandbox/agent
    python examples/brain_demo.py

演示内容:
    1. 预测-学习循环：Agent 执行任务前预测结果，执行后学习
    2. 有限工作记忆：信息超出容量时自动压缩
    3. 记忆整合（"睡眠"）：定期整理经验，发现规律
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.brain import Brain


def demo_prediction_loop():
    """演示 1：预测-学习循环"""
    print("=" * 60)
    print("  演示 1：预测-学习循环")
    print("  大脑通过预测错误来学习（Predictive Coding）")
    print("=" * 60)
    print()

    brain = Brain(project_id="demo", storage_dir="/tmp/brain_demo")

    # 模拟 Agent 执行一系列任务
    tasks = [
        # (action, context, actual_outcome, importance)
        ("run_tests", {"file": "auth.py"}, "fail: 2 errors in auth validation", 0.8),
        ("edit_file", {"file": "auth.py", "change": "fix validation"}, "success: file saved", 0.5),
        ("run_tests", {"file": "auth.py"}, "pass: all tests green", 0.6),
        ("run_tests", {"file": "auth.py"}, "pass: all tests green", 0.4),
        ("run_tests", {"file": "payment.py"}, "fail: timeout error", 0.9),
        ("edit_file", {"file": "payment.py", "change": "add retry"}, "success: file saved", 0.5),
        ("run_tests", {"file": "payment.py"}, "fail: still timeout", 0.8),
        ("edit_file", {"file": "payment.py", "change": "fix connection pool"}, "success: file saved", 0.5),
        ("run_tests", {"file": "payment.py"}, "pass: all tests green", 0.7),
        ("deploy", {"target": "staging"}, "success: deployed to staging", 0.6),
        ("run_tests", {"file": "auth.py"}, "pass: all tests green", 0.3),
        ("deploy", {"target": "production"}, "fail: health check failed", 0.9),
    ]

    print("Agent 开始执行任务序列...\n")

    for i, (action, context, actual, importance) in enumerate(tasks, 1):
        print(f"--- 第 {i} 步: {action} ---")
        
        # 1. 执行前预测
        prediction = brain.predict(action, context)
        print(f"  预测: {prediction.predicted_outcome} (信心 {prediction.confidence:.0%})")
        print(f"  依据: {prediction.reasoning}")

        # 2. 执行后学习
        error = brain.learn(
            action=action,
            context=context,
            prediction=prediction,
            actual_outcome=actual,
            importance=importance,
            emotional_valence=-0.5 if "fail" in actual else 0.3,
        )
        print(f"  实际: {actual}")
        print(f"  误差: {error.magnitude:.2f} (惊讶度: {error.surprise})")
        if error.magnitude > 0.3:
            print(f"  教训: {error.lesson}")
        print()

    # 显示学习结果
    print("\n" + "=" * 60)
    print("  学习结果")
    print("=" * 60)
    print(f"\n预测准确率: {brain._predictor.get_accuracy():.0%}")
    print(f"\n{brain._predictor.get_world_model_summary()}")


def demo_working_memory():
    """演示 2：有限工作记忆"""
    print("\n\n")
    print("=" * 60)
    print("  演示 2：有限工作记忆（容量 = 5）")
    print("  容量满了必须压缩 → 逼出抽象能力")
    print("=" * 60)
    print()

    brain = Brain(project_id="demo_wm", storage_dir="/tmp/brain_demo_wm", working_memory_capacity=5)

    # 模拟信息陆续进入
    info_stream = [
        ("用户要求: 重构 UserService 类", 0.9, "task"),
        ("UserService.py 有 500 行代码", 0.5, "context"),
        ("依赖: DatabasePool, CacheManager, Logger", 0.6, "context"),
        ("当前有 3 个 public 方法和 12 个 private 方法", 0.4, "context"),
        ("用户说: 要拆分成 UserAuth 和 UserProfile 两个类", 0.8, "task"),
        ("发现: UserService 还被 PaymentService 引用", 0.7, "context"),
        ("注意: 修改后需要更新 20 个测试文件", 0.6, "context"),
        ("insight: 可以先用接口抽象，再做拆分", 0.8, "insight"),
    ]

    for content, importance, category in info_stream:
        print(f"  输入: {content}")
        compressed = brain._working_memory.push(content, importance, category)
        if compressed:
            print(f"    → [压缩发生!] 生成摘要: '{compressed.content}'")
        print(f"    当前使用: {brain._working_memory.size}/{brain._working_memory.capacity}")
        print()

    print("\n工作记忆最终状态:")
    print(brain._working_memory.get_summary())

    # 测试回忆
    print("\n\n尝试回忆 'Database':")
    recalled = brain.recall("Database")
    for r in recalled:
        print(f"  回忆到: {r}")


def demo_consolidation():
    """演示 3：记忆整合（"睡眠"）"""
    print("\n\n")
    print("=" * 60)
    print("  演示 3：记忆整合（Agent 的'睡眠'）")
    print("  定期整理经验，发现隐藏规律")
    print("=" * 60)
    print()

    brain = Brain(project_id="demo_sleep", storage_dir="/tmp/brain_demo_sleep")

    # 模拟大量经验积累
    print("模拟积累经验...\n")
    
    experiences = [
        # auth.py 经常出问题
        ("edit_file", {"file": "auth.py"}, "success", 0.5),
        ("run_tests", {"file": "auth.py"}, "fail: null pointer", 0.7),
        ("edit_file", {"file": "auth.py"}, "success", 0.5),
        ("run_tests", {"file": "auth.py"}, "fail: type error", 0.7),
        ("edit_file", {"file": "auth.py"}, "success", 0.5),
        ("run_tests", {"file": "auth.py"}, "pass", 0.4),
        
        # payment.py 修改后经常需要 deploy
        ("edit_file", {"file": "payment.py"}, "success", 0.5),
        ("run_tests", {"file": "payment.py"}, "pass", 0.4),
        ("deploy", {"target": "staging"}, "success", 0.6),
        
        ("edit_file", {"file": "payment.py"}, "success", 0.5),
        ("run_tests", {"file": "payment.py"}, "pass", 0.4),
        ("deploy", {"target": "staging"}, "success", 0.6),
        
        ("edit_file", {"file": "payment.py"}, "success", 0.5),
        ("run_tests", {"file": "payment.py"}, "pass", 0.4),
        ("deploy", {"target": "staging"}, "fail: config missing", 0.8),
        
        # utils.py 比较稳定
        ("edit_file", {"file": "utils.py"}, "success", 0.3),
        ("run_tests", {"file": "utils.py"}, "pass", 0.3),
        ("edit_file", {"file": "utils.py"}, "success", 0.3),
        ("run_tests", {"file": "utils.py"}, "pass", 0.3),
    ]

    for action, context, outcome, importance in experiences:
        brain._consolidation.record_experience(
            action=action,
            context=context,
            outcome=outcome,
            importance=importance,
            emotional_valence=-0.5 if "fail" in outcome else 0.2,
        )

    print(f"已积累 {len(experiences)} 条经验")
    print()

    # 触发整合
    print("触发'睡眠'整合...\n")
    insights = brain.sleep()

    print(f"发现 {len(insights)} 条洞察:\n")
    for i, insight in enumerate(insights, 1):
        marker = "!!!" if insight.confidence > 0.6 else "..."
        print(f"  {i}. [{insight.category}] {marker} {insight.pattern}")
        print(f"     置信度: {insight.confidence:.0%}, 证据: {insight.evidence_count} 条")
        print()

    # 显示状态
    print("\n整合后状态:")
    print(brain._consolidation.get_summary())


def demo_full_workflow():
    """演示 4：完整工作流"""
    print("\n\n")
    print("=" * 60)
    print("  演示 4：完整工作流 — 三个模块协同")
    print("=" * 60)
    print()

    brain = Brain(project_id="demo_full", storage_dir="/tmp/brain_demo_full")

    # 模拟一个完整的任务
    print("任务：修复 user_service.py 的 bug\n")

    # 1. 聚焦任务
    brain.focus("修复 user_service.py 的 NoneType 错误", importance=0.9, category="task")
    brain.focus("错误发生在 get_user_profile() 方法", importance=0.7, category="context")
    brain.focus("用户反馈：偶发性，约 10% 的请求会触发", importance=0.6, category="context")

    print("当前关注点:", brain.get_focus())
    print()

    # 2. 获取建议
    advice = brain.get_advice("edit_file", {"file": "user_service.py"})
    print("历史经验建议:", advice if advice else "(首次操作，无历史经验)")
    print()

    # 3. 预测 + 执行 + 学习
    print("执行修复...")
    pred = brain.predict("edit_file", {"file": "user_service.py", "change": "add null check"})
    print(f"  预测: {pred.predicted_outcome} ({pred.confidence:.0%})")

    error = brain.learn(
        action="edit_file",
        context={"file": "user_service.py", "change": "add null check"},
        prediction=pred,
        actual_outcome="success: file saved",
        importance=0.6,
    )
    print(f"  结果: success")
    print()

    # 4. 运行测试
    print("运行测试...")
    pred = brain.predict("run_tests", {"file": "user_service.py"})
    print(f"  预测: {pred.predicted_outcome} ({pred.confidence:.0%})")

    error = brain.learn(
        action="run_tests",
        context={"file": "user_service.py"},
        prediction=pred,
        actual_outcome="pass: all 42 tests green",
        importance=0.7,
        emotional_valence=0.5,
    )
    print(f"  结果: pass!")
    print()

    # 5. 查看大脑状态
    print("\n" + brain.get_status_report())


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       Brain Module Demo — 类脑认知系统演示               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    demo_prediction_loop()
    demo_working_memory()
    demo_consolidation()
    demo_full_workflow()

    print("\n\n✅ 演示完成！")
    print("这三个模块让你的 Agent 具备了：")
    print("  1. 从经验中学习的能力（不再每次从零开始）")
    print("  2. 有限注意力（强制聚焦重要信息）")
    print("  3. 自动发现规律的能力（定期整理和顿悟）")
