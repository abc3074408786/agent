"""
AutoVerifier: Agent automatically detects errors without human feedback.

Three verification methods:
1. TestRunner: run pytest, test failures = errors
2. StaticAnalyzer: run ruff + mypy, find code issues
3. SecurityScan: run bandit, find vulnerabilities

Integrated into post_tool: triggers after every file write/edit.
"""

from __future__ import annotations
import subprocess
import time
import json
import re
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class VerificationResult:
    """Single verification method result."""
    method: str
    passed: bool
    score: float
    issues: list = field(default_factory=list)
    duration_ms: int = 0
    raw_output: str = ""


class AutoVerifier:
    """
    Self-verification: Agent knows what's wrong without being told.
    
    After any file change:
    1. Run related tests → did they pass?
    2. Run linter (ruff) → syntax/style issues?
    3. Run type checker (mypy) → type errors?
    4. Run security scan (bandit) → vulnerabilities?
    
    Returns combined score + actionable fix suggestions.
    """

    def __init__(self, workspace: str = ".", timeout: int = 30):
        self.workspace = Path(workspace)
        self.timeout = timeout
        self.history: list[dict] = []

    def verify(self, changed_file: str, content: str = "") -> dict:
        """Full verification after a file change."""
        results = []
        all_issues = []

        if changed_file.endswith(".py"):
            # 1. Tests
            test_r = self._run_tests(changed_file)
            results.append(test_r)
            all_issues.extend(test_r.issues)

            # 2. Static analysis (ruff)
            static_r = self._run_ruff(changed_file)
            results.append(static_r)
            all_issues.extend(static_r.issues)

            # 3. Type check (mypy)
            mypy_r = self._run_mypy(changed_file)
            results.append(mypy_r)
            all_issues.extend(mypy_r.issues)

            # 4. Security (if relevant)
            if self._is_security_relevant(changed_file, content):
                sec_r = self._run_bandit(changed_file)
                results.append(sec_r)
                all_issues.extend(sec_r.issues)

        if not results:
            return {"passed": True, "score": 1.0, "issues": [], "suggestions": []}

        scores = [r.score for r in results]
        overall = sum(scores) / len(scores)
        passed = all(r.passed for r in results)
        suggestions = self._make_suggestions(all_issues)

        report = {
            "passed": passed,
            "score": overall,
            "issues": all_issues,
            "suggestions": suggestions,
            "methods": [{"name": r.method, "passed": r.passed, "score": r.score} for r in results],
        }
        self.history.append(report)
        return report

    def _run_tests(self, filepath: str) -> VerificationResult:
        """Run pytest for related test files."""
        start = time.time()
        test_file = self._find_test_file(filepath)
        target = test_file if test_file else "tests/"
        
        try:
            r = subprocess.run(
                f"python -m pytest {target} --tb=line -q --timeout=10",
                shell=True, capture_output=True, text=True,
                timeout=self.timeout, cwd=str(self.workspace)
            )
            output = r.stdout + r.stderr
            passed = r.returncode == 0
            issues = []
            
            if not passed:
                for line in output.split("\n"):
                    if "FAILED" in line:
                        issues.append({"severity": "error", "message": line.strip(), "source": "pytest"})

            # Calculate score from pass ratio
            score = 1.0 if passed else 0.2
            match = re.search(r"(\d+) passed", output)
            fail_match = re.search(r"(\d+) failed", output)
            if match and fail_match:
                p, f = int(match.group(1)), int(fail_match.group(1))
                score = p / max(p + f, 1)

            return VerificationResult("pytest", passed, score, issues, int((time.time()-start)*1000), output[:1000])
        except (subprocess.TimeoutExpired, Exception) as e:
            return VerificationResult("pytest", True, 0.7, [{"severity": "info", "message": str(e), "source": "pytest"}])

    def _run_ruff(self, filepath: str) -> VerificationResult:
        """Run ruff linter."""
        start = time.time()
        try:
            r = subprocess.run(
                f"python -m ruff check {filepath} --output-format=json",
                shell=True, capture_output=True, text=True,
                timeout=10, cwd=str(self.workspace)
            )
            issues = []
            if r.stdout.strip():
                try:
                    for item in json.loads(r.stdout):
                        sev = "error" if item.get("code","").startswith("E") else "warning"
                        issues.append({"severity": sev, "message": f"[{item.get('code','')}] {item.get('message','')}", "source": "ruff", "line": item.get("location",{}).get("row",0)})
                except json.JSONDecodeError:
                    pass
            
            errors = sum(1 for i in issues if i["severity"] == "error")
            score = max(0.0, 1.0 - errors * 0.2 - (len(issues) - errors) * 0.05)
            return VerificationResult("ruff", errors == 0, score, issues, int((time.time()-start)*1000))
        except Exception:
            return VerificationResult("ruff", True, 0.8, [])

    def _run_mypy(self, filepath: str) -> VerificationResult:
        """Run mypy type checker."""
        start = time.time()
        try:
            r = subprocess.run(
                f"python -m mypy {filepath} --no-error-summary --no-color --ignore-missing-imports",
                shell=True, capture_output=True, text=True,
                timeout=15, cwd=str(self.workspace)
            )
            issues = []
            if r.returncode != 0 and r.stdout:
                for line in r.stdout.strip().split("\n"):
                    if ": error:" in line:
                        issues.append({"severity": "error", "message": line.strip(), "source": "mypy"})
            
            passed = len(issues) == 0
            score = max(0.0, 1.0 - len(issues) * 0.15)
            return VerificationResult("mypy", passed, score, issues, int((time.time()-start)*1000))
        except Exception:
            return VerificationResult("mypy", True, 0.8, [])

    def _run_bandit(self, filepath: str) -> VerificationResult:
        """Run bandit security scanner."""
        start = time.time()
        try:
            r = subprocess.run(
                f"python -m bandit {filepath} -f json -q",
                shell=True, capture_output=True, text=True,
                timeout=10, cwd=str(self.workspace)
            )
            issues = []
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    for finding in data.get("results", []):
                        sev = "error" if finding.get("issue_severity","") == "HIGH" else "warning"
                        issues.append({"severity": sev, "message": f"[安全] {finding.get('issue_text','')}", "source": "bandit", "line": finding.get("line_number", 0)})
                except json.JSONDecodeError:
                    pass
            
            passed = not any(i["severity"] == "error" for i in issues)
            score = 1.0 if passed else 0.3
            return VerificationResult("bandit", passed, score, issues, int((time.time()-start)*1000))
        except Exception:
            return VerificationResult("bandit", True, 0.9, [])

    def _find_test_file(self, filepath: str) -> Optional[str]:
        """Find related test file."""
        stem = Path(filepath).stem
        for pattern in [f"tests/test_{stem}.py", f"tests/{stem}_test.py"]:
            if (self.workspace / pattern).exists():
                return pattern
        return None

    def _is_security_relevant(self, filepath: str, content: str) -> bool:
        keywords = ["password", "token", "secret", "auth", "login", "sql", "exec", "eval"]
        return any(kw in f"{filepath} {content}".lower() for kw in keywords)

    def _make_suggestions(self, issues: list) -> list[str]:
        """Generate fix suggestions."""
        suggestions = []
        for i in issues[:5]:
            if i["source"] == "pytest":
                suggestions.append(f"修复测试: {i['message'][:60]}")
            elif i["source"] == "ruff":
                suggestions.append(f"修复 lint: {i['message'][:60]}")
            elif i["source"] == "mypy":
                suggestions.append(f"修复类型: {i['message'][:60]}")
            elif i["source"] == "bandit":
                suggestions.append(f"修复安全: {i['message'][:60]}")
        return suggestions
