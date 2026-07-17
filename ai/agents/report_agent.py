"""Aggregates structured analytics data into a short, decision-ready markdown report."""
from __future__ import annotations

from typing import Any

from ai.agents.base import AgentResult, BaseAgent
from ai.prompts.templates import REPORT_AGENT_SYSTEM


class ReportGeneratorAgent(BaseAgent):
    name = "report"
    description = "Summarizes analytics/usage data into a markdown report with a recommended action."
    capabilities = ["markdown-report", "trend-summary"]

    def run(self, query: str, context: dict[str, Any] | None = None) -> AgentResult:
        data = (context or {}).get("data", {})
        if not data:
            return AgentResult(
                output="No data was supplied to summarize. Pass `context.data` "
                "(e.g. an AnalyticsSnapshot) to generate a report.",
                metadata={"rows": 0},
            )

        headline = self._headline(data)
        bullets = self._bullets(data)
        action = self._recommended_action(data)

        prompt = f"Data: {data}\n\nQuestion: {query}"
        llm_output = self.llm.complete(REPORT_AGENT_SYSTEM, prompt)

        report = (
            f"## {headline}\n\n"
            + "\n".join(f"- {b}" for b in bullets)
            + f"\n\n**Recommended action:** {action}"
        )
        if llm_output and llm_output != prompt.strip():
            report += f"\n\n---\n{llm_output}"

        return AgentResult(output=report, metadata={"data_keys": list(data.keys())})

    @staticmethod
    def _headline(data: dict[str, Any]) -> str:
        if "ai_requests_total" in data:
            return f"{data['ai_requests_total']} AI requests served, ${data.get('estimated_cost_usd', 0):.2f} spent"
        return "Report summary"

    @staticmethod
    def _bullets(data: dict[str, Any]) -> list[str]:
        bullets = []
        if "active_users" in data:
            bullets.append(f"Active users: {data['active_users']}")
        if "avg_latency_ms" in data:
            bullets.append(f"Average latency: {data['avg_latency_ms']:.1f}ms")
        if "search_accuracy" in data:
            bullets.append(f"Search accuracy: {data['search_accuracy'] * 100:.1f}%")
        if "requests_by_agent" in data:
            top_agent = max(data["requests_by_agent"], key=data["requests_by_agent"].get, default=None)
            if top_agent:
                bullets.append(f"Most-used agent: {top_agent} ({data['requests_by_agent'][top_agent]} requests)")
        return bullets or ["No notable metrics available."]

    @staticmethod
    def _recommended_action(data: dict[str, Any]) -> str:
        if data.get("avg_latency_ms", 0) > 2000:
            return "Investigate latency — consider caching hot queries or scaling the retrieval tier."
        if data.get("search_accuracy", 1.0) < 0.7:
            return "Search accuracy is below target; review chunking size and re-index affected documents."
        return "Metrics are within healthy ranges — no action needed this cycle."
