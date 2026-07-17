# Architecture

## System overview

```mermaid
flowchart TB
    U["User"] --> FE["Frontend<br/>Next.js"]
    FE -->|JWT| BE["Backend<br/>FastAPI"]
    BE --> MW["Middleware<br/>auth · rate limit · logging · cost tracking"]
    MW --> ORCH["Agent Orchestrator<br/>(LangGraph-style router)"]
    ORCH --> DOC["Document Agent"]
    ORCH --> SQL["SQL Agent"]
    ORCH --> EMAIL["Email Agent"]
    ORCH --> REPORT["Report Generator"]
    ORCH --> CODE["Code Assistant"]
    ORCH --> KB["Knowledge Base Agent"]
    DOC --> RAG["Hybrid RAG<br/>semantic + keyword"]
    KB --> RAG
    EMAIL --> RAG
    RAG --> VDB[("Vector DB<br/>Pinecone / in-memory")]
    RAG --> LLM["OpenAI / Llama<br/>(deterministic fallback offline)"]
    SQL --> SQLITE[("Demo SQL DB<br/>read-only, whitelisted")]
    BE --> CACHE[("Redis<br/>response cache")]
    BE --> PG[("PostgreSQL<br/>users, metadata")]
    BE --> ADMIN["Admin Analytics<br/>usage · cost · latency · accuracy"]
    ORCH -.retrain.-> MLOPS["MLOps<br/>Model Registry · Drift Gate"]
    MLOPS -.weekly.-> AIRFLOW["Airflow DAG"]
```

## Infrastructure

```mermaid
flowchart LR
    GH["GitHub"] --> GA["GitHub Actions<br/>CI + weekly retrain"]
    GA --> DOCKER["Docker images"]
    DOCKER --> K8S["Kubernetes<br/>Deployment · HPA · Ingress"]
    DOCKER --> ECS["AWS ECS Fargate<br/>(Terraform-provisioned)"]
    ECS --> RDS[("RDS PostgreSQL")]
    ECS --> ELASTICACHE[("ElastiCache Redis")]
    ECS --> S3[("S3<br/>document uploads")]
    ECS --> CW["CloudWatch<br/>logs + alarms"]
    K8S --> PROM["Prometheus"]
    PROM --> GRAFANA["Grafana dashboards"]
```

## Agent routing flow

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI /chat
    participant Router as Orchestrator.route()
    participant Agent as Selected Agent
    participant RAG as Hybrid Retriever

    User->>API: POST /chat {message}
    API->>Router: route(message)
    Router->>Router: classify() - keyword rules or learned model
    Router->>Agent: agent.run(query, context)
    alt Document / Knowledge Base / Email
        Agent->>RAG: search(query, filters)
        RAG-->>Agent: ranked chunks + citations
    end
    Agent-->>Router: AgentResult(output, citations)
    Router-->>API: RouteResult(agent_used, latency_ms)
    API->>API: record analytics (tokens, latency, accuracy)
    API-->>User: ChatResponse
```

## Why hybrid search

Pure semantic search misses exact identifiers (ticket numbers, SKUs, error codes); pure keyword search misses paraphrases. `HybridRetriever` blends cosine similarity over embeddings with TF-IDF keyword scoring (default 60/40 weighting), which is why `document`/`knowledge_base` agent citations stay accurate even when a query mixes natural language with an exact term.

## Why a custom orchestrator instead of the `langgraph` package

The orchestrator is written as a small, dependency-free state graph (router node → 6 leaf agent nodes) rather than importing `langgraph` directly, so the entire platform — API, agents, and tests — runs offline with zero external services. The interface (`route()`, `classify()`) is the intended swap point: replacing it with `langgraph.StateGraph` is a contained change that doesn't touch any agent or API code.
