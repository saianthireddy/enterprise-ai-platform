import type { ChatMessage, Citation } from "@/lib/api";
import AgentBadge from "./AgentBadge";

export default function ChatBubble({
  message,
  agent,
  citations,
}: {
  message: ChatMessage;
  agent?: string;
  citations?: Citation[];
}) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-xl rounded-2xl px-4 py-3 text-sm ${
          isUser ? "bg-brand-600 text-white" : "border border-slate-800 bg-slate-900 text-slate-100"
        }`}
      >
        {!isUser && agent && (
          <div className="mb-1">
            <AgentBadge agent={agent} />
          </div>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
        {citations && citations.length > 0 && (
          <div className="mt-2 space-y-1 border-t border-slate-700 pt-2">
            {citations.map((c, i) => (
              <p key={i} className="text-xs text-slate-400">
                [{c.source}] {c.snippet}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
