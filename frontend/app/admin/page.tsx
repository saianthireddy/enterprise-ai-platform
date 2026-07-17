"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchAnalytics, getToken } from "@/lib/api";
import type { AnalyticsSnapshot } from "@/lib/api";
import MetricCard from "@/components/MetricCard";
import AgentBadge from "@/components/AgentBadge";

export default function AdminPage() {
  const router = useRouter();
  const [snapshot, setSnapshot] = useState<AnalyticsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    fetchAnalytics()
      .then(setSnapshot)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load analytics"));
  }, [router]);

  return (
    <main className="min-h-screen p-8">
      <h1 className="mb-1 text-2xl font-semibold text-white">Admin dashboard</h1>
      <p className="mb-6 text-sm text-slate-400">Live usage, cost, and quality metrics across all agents.</p>

      {error && (
        <p className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error} — this endpoint requires an admin account.
        </p>
      )}

      {snapshot && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="Active users" value={snapshot.active_users} />
            <MetricCard label="AI requests" value={snapshot.ai_requests_total} />
            <MetricCard label="Tokens used" value={snapshot.token_usage_total.toLocaleString()} />
            <MetricCard label="Est. cost" value={`$${snapshot.estimated_cost_usd.toFixed(4)}`} />
            <MetricCard label="Avg latency" value={`${snapshot.avg_latency_ms.toFixed(0)}ms`} />
            <MetricCard
              label="Search accuracy"
              value={`${(snapshot.search_accuracy * 100).toFixed(0)}%`}
            />
          </div>

          <h2 className="mb-3 mt-8 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Requests by agent
          </h2>
          <div className="space-y-2">
            {Object.entries(snapshot.requests_by_agent).map(([agent, count]) => (
              <div
                key={agent}
                className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/60 px-4 py-2"
              >
                <AgentBadge agent={agent} />
                <span className="text-sm text-slate-300">{count} requests</span>
              </div>
            ))}
            {Object.keys(snapshot.requests_by_agent).length === 0 && (
              <p className="text-sm text-slate-500">No requests recorded yet.</p>
            )}
          </div>
        </>
      )}
    </main>
  );
}
