# Deployment

## Local (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export PYTHONPATH=.:backend
uvicorn app.main:app --app-dir backend --reload

cd frontend && npm install && npm run dev
```

## Docker Compose

```bash
cp .env.example .env   # fill in OPENAI_API_KEY / PINECONE_API_KEY if using them
docker compose -f docker/docker-compose.yml up --build
```

Services: `backend` (:8000), `frontend` (:3000), `postgres` (:5432), `redis` (:6379).

## Kubernetes

```bash
kubectl create namespace enterprise-ai-platform
kubectl apply -f kubernetes/configmap.yaml
cp kubernetes/secret.yaml.example kubernetes/secret.yaml   # fill in real values, do not commit
kubectl apply -f kubernetes/secret.yaml
kubectl apply -f kubernetes/backend-deployment.yaml -f kubernetes/backend-service.yaml
kubectl apply -f kubernetes/frontend-deployment.yaml -f kubernetes/frontend-service.yaml
kubectl apply -f kubernetes/hpa.yaml
kubectl apply -f kubernetes/ingress.yaml
```

The backend HPA scales 3→12 replicas on 70% CPU / 80% memory. Both deployments carry readiness and liveness probes against `/health`.

## AWS (Terraform)

```bash
cd terraform
terraform init
terraform plan \
  -var="backend_image=<ecr-uri>:latest" \
  -var="frontend_image=<ecr-uri>:latest" \
  -var="acm_certificate_arn=<arn>"
terraform apply
```

Provisions: VPC (public + private subnets across 2 AZs), an ECS Fargate cluster running the backend behind an ALB with target-tracking autoscaling, RDS Postgres (encrypted, managed master password via Secrets Manager), ElastiCache Redis, an encrypted S3 bucket for document uploads, and CloudWatch log groups. The frontend is designed to deploy the same way (add an `aws_ecs_service.frontend` block, or serve it from Vercel/Amplify pointing at the ALB's API host).

## CI/CD

`.github/workflows/ci.yml` runs backend lint + tests (Python 3.11/3.12), a frontend production build, and both Docker image builds on every push/PR. `.github/workflows/train.yml` retrains the intent-router model weekly and uploads the updated registry as a build artifact.
