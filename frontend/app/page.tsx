import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="rounded-full border border-brand-500/40 bg-brand-500/10 px-4 py-1 text-xs font-medium text-brand-500">
        Enterprise AI Platform
      </div>
      <h1 className="max-w-2xl text-4xl font-bold text-white sm:text-5xl">
        One copilot for your PDFs, tickets, databases, and code.
      </h1>
      <p className="max-w-xl text-slate-400">
        RAG-grounded chat, six specialist agents, and an admin dashboard — all behind JWT + Google
        OAuth login with role-based access control.
      </p>
      <div className="flex gap-3">
        <Link
          href="/login"
          className="rounded-lg bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-600"
        >
          Sign in
        </Link>
        <a
          href="https://github.com/saianthireddy/enterprise-ai-platform"
          className="rounded-lg border border-slate-700 px-5 py-2.5 text-sm font-semibold text-slate-200 hover:bg-slate-900"
        >
          View on GitHub
        </a>
      </div>
    </main>
  );
}
