const AGENT_COLORS: Record<string, string> = {
  document: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  sql: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  email: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  report: "bg-purple-500/20 text-purple-300 border-purple-500/40",
  code: "bg-pink-500/20 text-pink-300 border-pink-500/40",
  knowledge_base: "bg-slate-500/20 text-slate-300 border-slate-500/40",
};

export default function AgentBadge({ agent }: { agent: string }) {
  const style = AGENT_COLORS[agent] ?? AGENT_COLORS.knowledge_base;
  return (
    <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>
      {agent.replace("_", " ")}
    </span>
  );
}
