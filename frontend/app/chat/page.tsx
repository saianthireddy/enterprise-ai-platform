"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, listAgents, sendChatMessage, uploadDocument } from "@/lib/api";
import type { AgentInfo, ChatMessage, Citation } from "@/lib/api";
import ChatBubble from "@/components/ChatBubble";
import AgentBadge from "@/components/AgentBadge";

interface Turn {
  message: ChatMessage;
  agent?: string;
  citations?: Citation[];
}

export default function ChatPage() {
  const router = useRouter();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [sending, setSending] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    listAgents().then(setAgents).catch(() => setAgents([]));
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;
    const userTurn: Turn = { message: { role: "user", content: input, created_at: new Date().toISOString() } };
    setTurns((prev) => [...prev, userTurn]);
    setSending(true);
    const query = input;
    setInput("");
    try {
      const res = await sendChatMessage(query, conversationId);
      setConversationId(res.conversation_id);
      setTurns((prev) => [...prev, { message: res.message, agent: res.agent_used, citations: res.citations }]);
    } catch (err) {
      setTurns((prev) => [
        ...prev,
        {
          message: {
            role: "assistant",
            content: `Error: ${err instanceof Error ? err.message : "request failed"}`,
            created_at: new Date().toISOString(),
          },
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadStatus("Uploading...");
    try {
      const doc = await uploadDocument(file);
      setUploadStatus(`Indexed "${doc.filename}" (${doc.chunk_count} chunks)`);
    } catch (err) {
      setUploadStatus(`Upload failed: ${err instanceof Error ? err.message : "unknown error"}`);
    }
  }

  return (
    <main className="flex min-h-screen">
      <aside className="hidden w-64 flex-col border-r border-slate-800 bg-slate-950 p-4 sm:flex">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Agents</h2>
        <div className="space-y-2">
          {agents.map((a) => (
            <div key={a.name} className="rounded-lg border border-slate-800 p-2">
              <AgentBadge agent={a.name} />
              <p className="mt-1 text-xs text-slate-400">{a.description}</p>
            </div>
          ))}
        </div>
        <div className="mt-6">
          <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
            Upload document
          </label>
          <input
            type="file"
            accept=".pdf,.docx,.xlsx,.pptx,.txt,.md"
            onChange={handleUpload}
            className="w-full text-xs text-slate-400"
          />
          {uploadStatus && <p className="mt-2 text-xs text-slate-500">{uploadStatus}</p>}
        </div>
      </aside>

      <section className="flex flex-1 flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {turns.length === 0 && (
            <p className="text-sm text-slate-500">
              Ask about an uploaded document, ticket counts, or say &quot;draft a reply to...&quot; —
              the router picks the right agent automatically.
            </p>
          )}
          {turns.map((t, i) => (
            <ChatBubble key={i} message={t.message} agent={t.agent} citations={t.citations} />
          ))}
          <div ref={bottomRef} />
        </div>
        <form onSubmit={handleSend} className="border-t border-slate-800 p-4">
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-white"
              placeholder="Ask anything..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button
              type="submit"
              disabled={sending}
              className="rounded-lg bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-60"
            >
              {sending ? "..." : "Send"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
