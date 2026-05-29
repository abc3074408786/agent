"""Amygdala - Risk Assessment + Emergency Interrupt"""


class Amygdala:
    """
    Rapid risk assessment and emergency response.
    
    Principles:
    - Fast path: evaluates danger BEFORE conscious processing
    - Fear conditioning: remembers what caused harm before
    - Override: can interrupt any action if risk too high
    - Calibration: adjusts sensitivity based on false alarm rate
    """

    def __init__(self, risk_threshold: float = 0.7):
        self.risk_threshold = risk_threshold
        self.fear_memories: list[dict] = []  # things that caused harm
        self.false_alarms: int = 0
        self.true_alarms: int = 0

        # Dangerous patterns (pre-wired)
        self.danger_patterns = [
            {"pattern": "rm -rf", "risk": 0.95, "reason": "可能删除所有文件"},
            {"pattern": "DROP TABLE", "risk": 0.9, "reason": "可能删除数据库表"},
            {"pattern": "force push", "risk": 0.8, "reason": "可能覆盖他人代码"},
            {"pattern": "chmod 777", "risk": 0.7, "reason": "安全风险: 开放所有权限"},
            {"pattern": "password", "risk": 0.5, "reason": "涉及敏感信息"},
            {"pattern": "sudo", "risk": 0.6, "reason": "超级用户权限"},
            {"pattern": "DELETE FROM", "risk": 0.8, "reason": "批量删除数据"},
            {"pattern": "> /dev/", "risk": 0.9, "reason": "可能破坏设备"},
            {"pattern": "format", "risk": 0.7, "reason": "可能格式化磁盘"},
            {"pattern": "api_key", "risk": 0.6, "reason": "可能泄露密钥"},
        ]

    def assess_risk(self, action: str, context: str = "") -> dict:
        """
        Rapid risk assessment. Returns risk level and whether to interrupt.
        """
        combined = f"{action} {context}".lower()
        max_risk = 0.0
        reasons = []

        # Check pre-wired danger patterns
        for dp in self.danger_patterns:
            if dp["pattern"].lower() in combined:
                max_risk = max(max_risk, dp["risk"])
                reasons.append(dp["reason"])

        # Check learned fear memories
        for fear in self.fear_memories:
            if any(keyword in combined for keyword in fear.get("keywords", [])):
                max_risk = max(max_risk, fear.get("risk", 0.7))
                reasons.append(f"历史教训: {fear.get('event', '')}")

        should_interrupt = max_risk >= self.risk_threshold

        return {
            "risk_level": max_risk,
            "should_interrupt": should_interrupt,
            "reasons": reasons,
            "action": "BLOCK" if should_interrupt else "ALLOW",
        }

    def learn_fear(self, event: str, keywords: list[str], risk: float = 0.7) -> None:
        """Learn from a bad experience (fear conditioning)."""
        self.fear_memories.append({
            "event": event,
            "keywords": keywords,
            "risk": risk,
        })
        self.true_alarms += 1

    def report_false_alarm(self) -> None:
        """Record that a risk assessment was wrong (calibration)."""
        self.false_alarms += 1
        # If too many false alarms, raise threshold
        if self.false_alarms > 5 and self.false_alarms > self.true_alarms:
            self.risk_threshold = min(0.95, self.risk_threshold + 0.05)

    def get_sensitivity(self) -> dict:
        total = self.true_alarms + self.false_alarms
        return {
            "threshold": self.risk_threshold,
            "true_alarms": self.true_alarms,
            "false_alarms": self.false_alarms,
            "precision": self.true_alarms / max(total, 1),
        }
