"""
EmbodiedAgent: Perception-Action Loop in Real Environments.

Extends beyond text generation to actual environment interaction:
- Execute actions and observe results
- Monitor environment state changes
- Maintain perception-action feedback loop
"""

from __future__ import annotations
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Optional

from agent.agi.base import AGIModule


class EnvironmentState:
    """Snapshot of the environment at a point in time."""
    def __init__(self):
        self.files_changed: list[str] = []
        self.processes: list[dict] = []
        self.metrics: dict[str, float] = {}
        self.timestamp: float = time.time()


class EmbodiedAgent(AGIModule):
    """
    Perception-Action loop: act → observe → update model → decide next.
    """

    def name(self) -> str:
        return "EmbodiedAgent"

    def __init__(self, data_dir: Path, workspace: str = "."):
        super().__init__(data_dir)
        self.workspace = Path(workspace)
        self.action_history: list[dict] = []
        self.sensors: list[Callable[[], dict]] = []
        self.max_history = 200

    def register_sensor(self, sensor: Callable[[], dict]) -> None:
        """Register an environment sensor."""
        self.sensors.append(sensor)

    # ─── Perception ───

    def perceive(self) -> dict:
        """Gather current environment state from all sensors."""
        state = {"timestamp": time.time(), "sensors": {}}
        for sensor in self.sensors:
            try:
                reading = sensor()
                state["sensors"].update(reading)
            except Exception as e:
                state["sensors"]["error"] = str(e)
        return state

    def detect_changes(self, before: dict, after: dict) -> list[str]:
        """Detect what changed between two states."""
        changes = []
        before_keys = set(str(k) for k in before.get("sensors", {}).keys())
        after_keys = set(str(k) for k in after.get("sensors", {}).keys())
        for key in after_keys - before_keys:
            changes.append(f"NEW: {key}")
        for key in before_keys - after_keys:
            changes.append(f"REMOVED: {key}")
        for key in before_keys & after_keys:
            if before["sensors"].get(key) != after["sensors"].get(key):
                changes.append(f"CHANGED: {key}")
        return changes

    # ─── Action ───

    def execute(self, action: str, args: dict | None = None) -> dict:
        """
        Execute an action in the real environment.
        Returns result + observation of what changed.
        """
        before = self.perceive()
        start = time.time()

        result = self._dispatch_action(action, args or {})

        duration = time.time() - start
        after = self.perceive()
        changes = self.detect_changes(before, after)

        record = {
            "action": action,
            "args": args,
            "result": result,
            "changes": changes,
            "duration_ms": int(duration * 1000),
            "timestamp": time.time(),
        }
        self.action_history.append(record)
        if len(self.action_history) > self.max_history:
            self.action_history = self.action_history[-self.max_history:]

        return record

    def _dispatch_action(self, action: str, args: dict) -> dict:
        """Route action to appropriate handler."""
        handlers = {
            "bash": self._action_bash,
            "file_write": self._action_file_write,
            "file_read": self._action_file_read,
            "http": self._action_http,
        }
        handler = handlers.get(action)
        if handler:
            return handler(args)
        return {"error": f"Unknown action: {action}"}

    # ─── Built-in Actions ───

    def _action_bash(self, args: dict) -> dict:
        """Execute bash command."""
        cmd = args.get("command", "")
        timeout = args.get("timeout", 30)
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(self.workspace)
            )
            return {
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:2000],
                "exit_code": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"error": "timeout", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    def _action_file_write(self, args: dict) -> dict:
        """Write content to a file."""
        path = self.workspace / args.get("path", "")
        content = args.get("content", "")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"success": True, "path": str(path)}
        except Exception as e:
            return {"error": str(e), "success": False}

    def _action_file_read(self, args: dict) -> dict:
        """Read a file."""
        path = self.workspace / args.get("path", "")
        try:
            content = path.read_text(encoding="utf-8")
            return {"success": True, "content": content[:10000]}
        except Exception as e:
            return {"error": str(e), "success": False}

    def _action_http(self, args: dict) -> dict:
        """Make HTTP request."""
        import urllib.request
        url = args.get("url", "")
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = resp.read().decode("utf-8")[:5000]
                return {"success": True, "status": resp.status, "body": body}
        except Exception as e:
            return {"error": str(e), "success": False}

    # ─── Feedback Loop ───

    def act_and_learn(self, action: str, args: dict, world_model=None) -> dict:
        """
        Full perception-action-learning loop:
        1. Predict what will happen (if world model available)
        2. Execute action
        3. Compare prediction with reality
        4. Update world model
        """
        prediction = None
        if world_model:
            predictions = world_model.predict(action, args)
            prediction = predictions[0]["effect"] if predictions else None

        result = self.execute(action, args)

        # Learn from result
        if world_model:
            actual_effect = "success" if result.get("result", {}).get("success") else "failure"
            world_model.observe(action, args, actual_effect)
            if prediction and prediction != actual_effect:
                world_model.observe_no_effect(action, prediction)

        return {**result, "prediction": prediction, "prediction_correct": prediction == result.get("result", {}).get("success")}
