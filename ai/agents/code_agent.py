"""Explains, reviews, and lightly generates code. Static analysis via `ast`
catches obvious issues (bare except, eval/exec use) before any LLM call."""
from __future__ import annotations

import ast
from typing import Any

from ai.agents.base import AgentResult, BaseAgent
from ai.prompts.templates import CODE_AGENT_SYSTEM


class CodeAssistantAgent(BaseAgent):
    name = "code"
    description = "Explains, reviews, and drafts small code snippets with static-analysis flags."
    capabilities = ["code-review", "static-analysis", "snippet-generation"]

    def _static_review(self, code: str) -> list[str]:
        findings: list[str] = []
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return [f"Syntax error: {exc.msg} (line {exc.lineno})"]

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append(f"Bare `except:` at line {node.lineno} — catch a specific exception.")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec"}:
                    findings.append(f"Use of `{node.func.id}()` at line {node.lineno} — potential code-injection risk.")
            if isinstance(node, ast.FunctionDef) and not ast.get_docstring(node):
                findings.append(f"Function `{node.name}` at line {node.lineno} has no docstring.")
        return findings

    def run(self, query: str, context: dict[str, Any] | None = None) -> AgentResult:
        code = (context or {}).get("code", "")
        findings = self._static_review(code) if code else []

        prompt = f"Code:\n{code}\n\nRequest: {query}"
        llm_output = self.llm.complete(CODE_AGENT_SYSTEM, prompt)

        if llm_output and llm_output != prompt.strip():
            output = llm_output
        elif code:
            summary = f"Reviewed {len(code.splitlines())} lines."
            issues = "\n".join(f"- {f}" for f in findings) if findings else "- No obvious issues found."
            output = f"{summary}\n\n{issues}"
        else:
            output = "Provide `context.code` with a snippet to review, explain, or extend."

        return AgentResult(output=output, metadata={"findings": findings, "finding_count": len(findings)})
