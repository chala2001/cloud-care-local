# Phase 7 — CI/CD: GitHub Actions Locally with act

## What you learn
- What `act` is and how it runs GitHub Actions on your laptop
- Understand the existing cloud-care-k8s workflow structure
- Write a simple local workflow for cloud-care-local
- Run the workflow with `act` and watch it build + deploy
- Understand the difference between local `act` and real GitHub Actions

---

## What is act?

In cloud-care-k8s, GitHub Actions ran on GitHub's cloud servers.
Every push triggered a runner that built the Docker image, pushed to ECR,
and ran `helm upgrade` on EKS.

**`act`** is a tool that runs the same `.github/workflows/*.yml` files
on your laptop using Docker containers as the runner environment.

```
cloud-care-k8s CI/CD:

  Git push → GitHub → GitHub Actions runner (cloud) → ECR → EKS

cloud-care-local CI/CD with act:

  act command → Docker container (local runner) → minikube image → minikube
```

You don't push to GitHub. `act` simulates the entire GitHub Actions environment locally.

---

## Step 1 — Install act

```bash
# Check if already installed
which act && act --version

# If not installed:
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

Or with Go:
```bash
go install github.com/nektos/act@latest
```

Verify:
```bash
act --version
# act version 0.2.x
```

---

## Step 2 — Understand the cloud-care-k8s workflow

Before writing our own, understand what the existing workflow does.
Read the patient-service deploy workflow:

```bash
cat /home/chalaka/cloud-care-both/cloud-care-k8s/.github/workflows/deploy-patient-service.yml
```

Key sections to notice:
- `on: push: paths:` — triggers only when patient-service files change
- `permissions: id-token: write` — OIDC auth to AWS (not needed locally)
- `aws-actions/configure-aws-credentials` — gets AWS credentials
- `docker build + docker push` — builds image and pushes to ECR
- `helm upgrade --install` — deploys to EKS

For local, we skip all AWS steps. Instead:
- Build image directly into minikube's Docker daemon
- Run `helm upgrade` pointing at local chart

---

## Step 3 — Create the workflows directory

```bash
mkdir -p .github/workflows
```

---

## Step 4 — Write a local workflow for patient-service

Create `.github/workflows/deploy-patient-service-local.yml`:

```yaml
name: Deploy patient-service (local)

on:
  push:
    paths:
      - 'services/patient-service/**'
      - 'helm/patient-service/**'
      - '.github/workflows/deploy-patient-service-local.yml'
  workflow_dispatch:   # allow manual trigger

env:
  SERVICE: patient-service
  NAMESPACE: dev
  IMAGE_TAG: local

jobs:
  deploy:
    name: Build and deploy patient-service
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image
        run: |
          docker build \
            -t ${{ env.SERVICE }}:${{ env.IMAGE_TAG }} \
            ./services/${{ env.SERVICE }}
          echo "Built image: ${{ env.SERVICE }}:${{ env.IMAGE_TAG }}"

      - name: Set up Helm
        uses: azure/setup-helm@v4
        with:
          version: v3.14.0

      - name: Deploy with Helm
        run: |
          helm upgrade --install ${{ env.SERVICE }} \
            helm/${{ env.SERVICE }} \
            --namespace ${{ env.NAMESPACE }} \
            --create-namespace \
            -f helm/${{ env.SERVICE }}/values-local.yaml \
            --set image.tag=${{ env.IMAGE_TAG }}

      - name: Verify deployment
        run: |
          kubectl get pods -n ${{ env.NAMESPACE }} -l app=${{ env.SERVICE }}
```

---

## Step 5 — Understand what act needs to work

`act` runs workflows inside Docker containers. For our workflow to deploy to minikube:

**Problem:** The `act` runner container is isolated — it can't talk to your minikube cluster
by default. We need to pass the kubeconfig so `helm` and `kubectl` inside the runner
can reach minikube.

**Solution:** Use `act`'s `--secret` flag to pass the kubeconfig content.

Get your kubeconfig:
```bash
kubectl config view --raw > /tmp/kubeconfig-local.yaml
cat /tmp/kubeconfig-local.yaml
```

---

## Step 6 — Run the workflow with act

First, do a dry run to see what steps would execute:

```bash
act push --dryrun \
  -W .github/workflows/deploy-patient-service-local.yml
```

You'll see the jobs and steps listed without actually running them.

Now run for real:

```bash
act push \
  -W .github/workflows/deploy-patient-service-local.yml \
  --secret KUBECONFIG="$(cat /tmp/kubeconfig-local.yaml)"
```

`act` will:
1. Pull the runner Docker image (first time takes a few minutes)
2. Execute each step in order
3. Show you the output — same as GitHub Actions logs

---

## Step 7 — Watch the workflow run

You'll see output like:
```
[Deploy patient-service (local)/Build and deploy patient-service] ⭐ Run Checkout code
[Deploy patient-service (local)/Build and deploy patient-service] ✅ Success - Checkout code
[Deploy patient-service (local)/Build and deploy patient-service] ⭐ Run Build Docker image
[Deploy patient-service (local)/Build and deploy patient-service]   docker build -t patient-service:local ./services/patient-service
[Deploy patient-service (local)/Build and deploy patient-service] ✅ Success - Build Docker image
[Deploy patient-service (local)/Build and deploy patient-service] ⭐ Run Deploy with Helm
[Deploy patient-service (local)/Build and deploy patient-service] ✅ Success - Deploy with Helm
[Deploy patient-service (local)/Build and deploy patient-service] ⭐ Run Verify deployment
[Deploy patient-service (local)/Build and deploy patient-service] ✅ Success - Verify deployment
```

After it finishes:
```bash
kubectl get pods -n dev -l app=patient-service
```

The pod should be running with the freshly built image.

---

## Step 8 — Simulate a code change and re-deploy

Make a small change to patient-service to prove the pipeline works end to end.

Edit `services/patient-service/app/main.py` — find the health endpoint and add a version field:

```python
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "patient-service",
        "version": "2.1-local"        # ← change this
    }
```

Now re-run the workflow:
```bash
act push \
  -W .github/workflows/deploy-patient-service-local.yml \
  --secret KUBECONFIG="$(cat /tmp/kubeconfig-local.yaml)"
```

After it completes:
```bash
kubectl port-forward svc/patient-service 8001:8001 -n dev &
sleep 2
curl http://localhost:8001/health
```

You should see `"version": "2.1-local"` in the response — the pipeline rebuilt the image
and redeployed automatically.

---

## Step 9 — Add a test step to the workflow

Real CI/CD pipelines run tests before deploying. Add a test step to your workflow.

Edit `.github/workflows/deploy-patient-service-local.yml` — add this step between
"Build Docker image" and "Deploy with Helm":

```yaml
      - name: Run unit tests
        run: |
          cd services/${{ env.SERVICE }}
          pip install -r requirements.txt -q
          pytest tests/ -v --tb=short
```

Run the workflow again. You'll see the tests execute as part of the pipeline.
If tests fail, the deploy step never runs — this is the core value of CI/CD.

To prove it: break a test temporarily:

```bash
# Open services/patient-service/tests/test_patients.py
# Change one assertion to fail, then run:
act push \
  -W .github/workflows/deploy-patient-service-local.yml \
  --secret KUBECONFIG="$(cat /tmp/kubeconfig-local.yaml)"
```

You'll see the pipeline stop at the test step — deploy never happens.
Fix the test and run again — everything passes and deploy continues.

---

## Step 10 — Understand act vs real GitHub Actions

| | Real GitHub Actions | act (local) |
|-|-------------------|------------|
| Trigger | Git push to GitHub | `act push` command |
| Runner | GitHub's cloud servers | Docker container on your laptop |
| Image registry | AWS ECR | minikube Docker daemon |
| Kubernetes cluster | EKS | minikube |
| Secrets | GitHub Secrets (web UI) | `--secret` flag or `.secrets` file |
| Artifacts | Uploaded to GitHub | Local only |
| Parallelism | Multiple jobs in parallel | Limited by laptop CPU |
| Cost | GitHub free tier / paid minutes | Free |

The workflow YAML is **identical**. Only the infrastructure behind it changes.
This means when you push to GitHub later, the same workflow works — you just add
AWS credentials and replace the local Docker/kubectl steps with the AWS equivalents.

---

## Step 11 — Create a .secrets file (cleaner than --secret flag)

Instead of typing `--secret` every time, create a `.secrets` file:

```bash
cat > .secrets << EOF
KUBECONFIG=$(cat /tmp/kubeconfig-local.yaml | base64 -w0)
EOF
```

Update the workflow to decode it:
```yaml
      - name: Set up kubeconfig
        run: |
          mkdir -p ~/.kube
          echo "${{ secrets.KUBECONFIG }}" | base64 -d > ~/.kube/config
```

Now run with just:
```bash
act push -W .github/workflows/deploy-patient-service-local.yml
```

**Important:** Add `.secrets` to `.gitignore` — never commit this file:
```bash
echo ".secrets" >> .gitignore
```

---

## What you've built across all 7 phases

```
Phase 0  →  minikube cluster running locally
Phase 1  →  understand raw Kubernetes YAML (pods, deployments, services)
Phase 2  →  database (PostgreSQL StatefulSet + PVC + Secrets)
Phase 3  →  Helm (package manager — install, upgrade, rollback)
Phase 4  →  Ingress (single entry point, URL routing)
Phase 5  →  Observability (Prometheus metrics + Loki logs + Grafana dashboards)
Phase 6  →  HPA (auto-scaling based on CPU)
Phase 7  →  CI/CD (automated build + deploy pipeline with act)
```

This is the complete production-grade Kubernetes stack — running for free on your laptop.
Everything here is directly transferable to any cloud provider (AWS EKS, GCP GKE, Azure AKS).

---

## Key concepts learned

| Concept | What it means |
|---------|--------------|
| `act` | Runs GitHub Actions workflows locally using Docker |
| `workflow_dispatch` | Allows manual workflow trigger (no git push needed) |
| `--dryrun` | Preview what steps would run without executing them |
| `.secrets` file | Local equivalent of GitHub Secrets for act |
| CI gate | Tests run before deploy — pipeline stops if tests fail |
| `on: push: paths:` | Workflow only triggers when specific files change |

---

## Done when
- `act --version` works
- You ran the workflow with `act push` and saw all steps pass
- You made a code change, re-ran act, and saw the new version deployed
- You added a test step and proved the pipeline stops on test failure
- You understand the difference between act and real GitHub Actions
