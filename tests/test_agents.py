import pytest

from ai.agents.code_agent import CodeAssistantAgent
from ai.agents.email_agent import EmailAgent
from ai.agents.knowledge_base_agent import KnowledgeBaseAgent
from ai.agents.orchestrator import AgentOrchestrator, classify
from ai.agents.report_agent import ReportGeneratorAgent
from ai.agents.sql_agent import SQLAgent, validate_sql
from ai.embeddings.embedder import HashingEmbedder
from ai.rag.hybrid_search import HybridRetriever
from ai.rag.vector_store_factory import VectorRecord, build_vector_store
from scripts.seed_demo_db import seed


@pytest.fixture()
def retriever():
    embedder = HashingEmbedder(dimensions=64)
    store = build_vector_store("memory")
    r = HybridRetriever(store, embedder)
    text = "Enterprise customers get a 60-day refund window instead of the standard 30 days."
    r.index([
        VectorRecord(
            id="policy-1", text=text, embedding=embedder.embed_one(text),
            metadata={"doc_id": "policy-doc", "source": "refund_policy.pdf"},
        )
    ])
    return r


@pytest.fixture()
def demo_db(tmp_path):
    db_path = tmp_path / "demo.db"
    seed(db_path)
    return db_path


def test_knowledge_base_agent_returns_citations(retriever):
    agent = KnowledgeBaseAgent(retriever)
    result = agent.run("What is the refund window for enterprise customers?")
    assert result.citations
    assert result.citations[0]["source"] == "refund_policy.pdf"


def test_knowledge_base_agent_handles_empty_index():
    embedder = HashingEmbedder(dimensions=32)
    empty_retriever = HybridRetriever(build_vector_store("memory"), embedder)
    agent = KnowledgeBaseAgent(empty_retriever)
    result = agent.run("anything")
    assert result.metadata["hits"] == 0


def test_validate_sql_rejects_non_select():
    with pytest.raises(ValueError):
        validate_sql("DELETE FROM employees")


def test_validate_sql_rejects_unlisted_table():
    with pytest.raises(ValueError):
        validate_sql("SELECT * FROM secrets")


def test_validate_sql_accepts_whitelisted_select():
    validate_sql("SELECT COUNT(*) FROM tickets WHERE status = 'open'")


def test_sql_agent_answers_ticket_count(demo_db):
    agent = SQLAgent(db_path=demo_db)
    result = agent.run("How many open tickets are there?")
    assert "open_tickets" in result.output
    assert result.metadata["sql"] is not None


def test_sql_agent_answers_department_filter(demo_db):
    agent = SQLAgent(db_path=demo_db)
    result = agent.run("employees in Sales")
    assert result.metadata["row_count"] == 2


def test_sql_agent_unrecognized_query_returns_help(demo_db):
    agent = SQLAgent(db_path=demo_db)
    result = agent.run("what's the weather today")
    assert result.metadata["sql"] is None


def test_email_agent_drafts_reply_with_recipient(retriever):
    agent = EmailAgent(retriever)
    result = agent.run("Explain our refund window", context={"recipient": "Jamie"})
    assert "Jamie" in result.output


def test_report_agent_flags_high_latency():
    agent = ReportGeneratorAgent()
    result = agent.run("summarize", context={"data": {"avg_latency_ms": 3000, "ai_requests_total": 10}})
    assert "latency" in result.output.lower()


def test_report_agent_healthy_metrics_no_action():
    agent = ReportGeneratorAgent()
    data = {"avg_latency_ms": 200, "search_accuracy": 0.95, "ai_requests_total": 5}
    result = agent.run("summarize", context={"data": data})
    assert "no action needed" in result.output.lower()


def test_code_agent_flags_bare_except():
    agent = CodeAssistantAgent()
    code = "def f():\n    try:\n        pass\n    except:\n        pass\n"
    result = agent.run("review this", context={"code": code})
    assert result.metadata["finding_count"] >= 1


def test_code_agent_flags_eval_usage():
    agent = CodeAssistantAgent()
    code = "def run(x):\n    return eval(x)\n"
    result = agent.run("review this", context={"code": code})
    assert any("eval" in f for f in result.metadata["findings"])


@pytest.mark.parametrize(
    "query,expected",
    [
        ("How many open tickets are there?", "sql"),
        ("Draft a reply to this customer email", "email"),
        ("Give me a weekly summary report", "report"),
        ("Review this Python function for bugs", "code"),
        ("What does the uploaded PDF say about refunds?", "document"),
        ("What's our vacation policy?", "knowledge_base"),
    ],
)
def test_classify_routes_to_expected_agent(query, expected):
    assert classify(query) == expected


def test_orchestrator_routes_and_executes(retriever):
    orchestrator = AgentOrchestrator(retriever)
    route_result = orchestrator.route("What's our vacation policy?")
    assert route_result.agent_used == "knowledge_base"
    assert route_result.latency_ms >= 0


def test_orchestrator_lists_six_agents(retriever):
    orchestrator = AgentOrchestrator(retriever)
    assert len(orchestrator.list_agents()) == 6
