# cloud-care-local — Learning Roadmap

## Goal
Learn Kubernetes hands-on with zero AWS cost. Same 4 services from cloud-care-k8s,
running locally on minikube. Go slow. Break things. Understand everything.

## Stack
- **minikube** — local Kubernetes cluster (replaces EKS)
- **Docker** — build images locally (replaces ECR)
- **Helm** — deploy services (same charts as cloud-care-k8s)
- **NGINX Ingress** — route traffic (replaces AWS ALB)
- **PostgreSQL pod** — database (replaces RDS)
- **Prometheus + Grafana + Loki** — observability (same as cloud-care-k8s)
- **GitHub Actions + act** — run CI/CD locally (replaces cloud runners)

---

## Phase 0 — Setup (doc: 01-setup.md)
**What you learn:** Install all tools, start minikube, understand what's running

- Install: minikube, kubectl, helm, docker
- `minikube start` — your local Kubernetes cluster
- `kubectl get nodes` — see your single node
- `minikube dashboard` — visual UI for everything
- Enable addons: ingress, metrics-server

**Done when:** `kubectl get nodes` shows 1 node Ready

---

## Phase 1 — Deploy First Service with Raw kubectl (doc: 02-kubectl-basics.md)
**What you learn:** Understand pods, deployments, services WITHOUT Helm first

- Write a Deployment YAML for patient-service by hand
- Write a Service YAML (ClusterIP)
- `kubectl apply -f` — deploy it
- `kubectl get pods` — see it running
- `kubectl logs` — see application logs
- `kubectl exec -it` — get inside a running pod
- `kubectl describe pod` — debug when something breaks
- `kubectl delete` — clean up

**Why this phase exists:** Helm hides the complexity. You must understand raw k8s first.

**Done when:** patient-service pod is running and you can curl it from inside the cluster

---

## Phase 2 — Databases Inside Kubernetes (doc: 03-database.md)
**What you learn:** Run PostgreSQL as a pod, connect services to it

- Deploy PostgreSQL using `helm install` (bitnami chart)
- Create a Kubernetes Secret for DB credentials (manual — no ESO needed)
- Connect patient-service to PostgreSQL using env vars
- `kubectl exec` into postgres pod and run `psql` commands
- Understand PersistentVolumeClaims — how data survives pod restarts

**Done when:** patient-service connects to PostgreSQL, you can create a patient via curl

---

## Phase 3 — Deploy All Services with Helm (doc: 04-helm.md)
**What you learn:** Helm install, upgrade, rollback, values, templating

- `helm install` — deploy a chart
- `helm list` — see all releases
- `helm upgrade` — update a running release
- `helm rollback` — go back to previous version
- `helm uninstall` — remove a release
- `helm template` — see what YAML Helm generates
- values-local.yaml — create local environment values
- Deploy all 4 services with Helm

**Done when:** All 4 services running, you can upgrade and rollback patient-service by hand

---

## Phase 4 — Ingress (doc: 05-ingress.md)
**What you learn:** Route external traffic into the cluster

- NGINX Ingress Controller (minikube addon)
- Write an Ingress resource
- `minikube tunnel` — expose ingress to localhost
- Hit your APIs at http://localhost/patients
- Understand how requests flow: browser → ingress → service → pod

**Done when:** All 4 service APIs accessible at http://localhost from your browser

---

## Phase 5 — Observability (doc: 06-observability.md)
**What you learn:** Prometheus, Grafana, Loki — explore at your own pace

- Install kube-prometheus-stack with Helm
- Install loki-stack with Helm
- `kubectl port-forward` — access Grafana at localhost:3000
- Explore pre-built Kubernetes dashboards
- Write your own PromQL queries:
  - `up{job=~"cloudcare.*"}` — are services up?
  - `rate(http_requests_total[5m])` — request rate
  - `histogram_quantile(0.99, ...)` — P99 latency
- Explore Loki — search logs by service name, filter by level
- Build a custom Grafana dashboard from scratch
- Apply AlertManager rules — understand when alerts fire

**Done when:** You can answer "is my cluster healthy?" just by looking at Grafana

---

## Phase 6 — HPA (doc: 07-hpa.md)
**What you learn:** Auto-scaling under load, watch it happen in real time

- Enable metrics-server (minikube addon)
- Apply HPA for patient-service (cpu > 50%)
- Run a load generator pod: `kubectl run load...`
- Watch `kubectl get hpa -w` in real time
- Watch pods scale up: 1 → 2 → 3
- Stop load, watch scale down after 5 minutes
- Understand cooldown windows

**Done when:** You've watched the full scale-up and scale-down cycle yourself

---

## Phase 7 — CI/CD Locally (doc: 08-cicd.md)
**What you learn:** Run GitHub Actions pipelines on your own machine

- Install `act` — runs GitHub Actions locally
- Set up a self-hosted runner (optional — for real GitHub triggers)
- Run the deploy-patient-service pipeline locally with `act`
- Understand each step: build image → load into minikube → helm upgrade
- Trigger a deploy by pushing to GitHub, watch it run

**Done when:** Pushing a code change triggers a pipeline that deploys to minikube

---

## Learning Order
```
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
Setup     kubectl    Database   Helm       Ingress    Grafana    HPA       CI/CD
1 day     2 days     1 day      2 days     1 day      3 days     1 day     2 days
```

Total: ~2 weeks at a comfortable pace, zero AWS cost.

---

## Key Difference from cloud-care-k8s
In cloud-care-k8s we went fast because EKS costs money.
Here there is no cost — take your time on each phase.
Read the error messages. Understand why things fail. That's the real learning.
