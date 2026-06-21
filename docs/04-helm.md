# Phase 3 — Deploy All Services with Helm

## What you learn
- What Helm is and why we use it
- `helm install` / `helm upgrade` / `helm rollback` / `helm uninstall`
- `helm template` — see what YAML Helm generates
- Create `values-local.yaml` for local environment overrides
- Deploy all 4 services with Helm

---

## What is Helm?

In Phase 1 you wrote raw YAML files by hand.
In Phase 2 you did the same for patient-service with a real image.

**The problem:** If you have 4 services, each needing a Deployment + Service + Secret,
that's 12 YAML files. And if you want dev vs prod differences (1 replica vs 2 replicas),
you'd need 24 files.

**Helm solves this** by using templates with variables:

```
helm/patient-service/
├── Chart.yaml          ← chart metadata (name, version)
├── values.yaml         ← default variable values
├── values-local.yaml   ← local overrides (you create this)
└── templates/
    ├── deployment.yaml ← uses {{ .Values.replicas }}, {{ .Values.image.tag }} etc.
    ├── service.yaml
    └── hpa.yaml
```

Instead of editing YAML directly, you change values.

---

## Step 1 — Copy Helm charts from cloud-care-k8s

The Helm charts already exist in cloud-care-k8s. Copy them:

```bash
cp -r /home/chalaka/cloud-care-both/cloud-care-k8s/helm \
      /home/chalaka/cloud-care-both/cloud-care-local/
```

Verify:
```bash
ls helm/
# patient-service  appointment-service  audit-service  notification-service
```

---

## Step 2 — Understand the chart structure

Look at patient-service chart:

```bash
ls helm/patient-service/
cat helm/patient-service/Chart.yaml
cat helm/patient-service/values.yaml
cat helm/patient-service/values-prod.yaml
```

Read through `values.yaml` — notice fields like:
- `image.repository` — where to pull the image from
- `image.tag` — which version
- `replicaCount` — how many pods
- `service.port` — which port

These variables are used inside `templates/deployment.yaml` like `{{ .Values.image.tag }}`.

---

## Step 3 — See what Helm generates (without applying)

```bash
helm template patient-service helm/patient-service \
  -f helm/patient-service/values.yaml
```

This prints the raw YAML that Helm would apply. Compare it to the YAML you wrote by hand
in Phase 1 and Phase 2 — it's the same structure, just generated from templates.

**This command is your best friend for debugging Helm issues.**

---

## Step 4 — Create values-local.yaml for each service

The existing `values-prod.yaml` uses AWS ECR images and IRSA. For local we need different values.

Create `helm/patient-service/values-local.yaml`:

```yaml
replicaCount: 1

image:
  repository: patient-service
  tag: local
  pullPolicy: Never       # use locally built minikube image

service:
  port: 8001

env:
  databaseSecretName: patient-service-db-secret

resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"

hpa:
  enabled: false          # disable HPA for now (Phase 6)

serviceAccount:
  create: false           # no IRSA needed locally
```

Create `helm/appointment-service/values-local.yaml`:

```yaml
replicaCount: 1

image:
  repository: appointment-service
  tag: local
  pullPolicy: Never

service:
  port: 8002

env:
  databaseSecretName: appointment-service-db-secret

resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"

hpa:
  enabled: false

serviceAccount:
  create: false
```

Create `helm/audit-service/values-local.yaml`:

```yaml
replicaCount: 1

image:
  repository: audit-service
  tag: local
  pullPolicy: Never

service:
  port: 8003

resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"

hpa:
  enabled: false

serviceAccount:
  create: false
```

Create `helm/notification-service/values-local.yaml`:

```yaml
replicaCount: 1

image:
  repository: notification-service
  tag: local
  pullPolicy: Never

service:
  port: 8004

resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"

hpa:
  enabled: false

serviceAccount:
  create: false
```

---

## Step 5 — Build all 4 Docker images into minikube

```bash
# Point docker to minikube's daemon
eval $(minikube docker-env)

# Build all 4 images
docker build -t patient-service:local ./services/patient-service
docker build -t appointment-service:local ./services/appointment-service
docker build -t audit-service:local ./services/audit-service
docker build -t notification-service:local ./services/notification-service

# Verify all 4 are there
docker images | grep ":local"
```

---

## Step 6 — Create secrets for all services

appointment-service also needs a DB secret.
audit-service uses DynamoDB (we'll fake it locally — it logs instead of sending).
notification-service uses SES (also faked locally).

```bash
# appointment-service DB secret
kubectl create secret generic appointment-service-db-secret \
  --from-literal=DATABASE_URL="postgresql://patient_svc:devpassword123@postgresql:5432/cloudcare" \
  --namespace dev

# audit-service — set LOCAL_DEV mode (logs audit events instead of DynamoDB)
kubectl create secret generic audit-service-secret \
  --from-literal=DYNAMODB_ENDPOINT_URL="http://localhost:8000" \
  --namespace dev

# notification-service — set LOCAL_DEV mode (logs emails instead of SES)
kubectl create secret generic notification-service-secret \
  --from-literal=LOCAL_DEV="true" \
  --namespace dev
```

---

## Step 7 — Deploy all 4 services with Helm

```bash
# Remove the old raw kubectl patient-service if still running
kubectl delete deployment patient-service -n dev 2>/dev/null || true
kubectl delete service patient-service -n dev 2>/dev/null || true

# Install all 4 services
helm upgrade --install patient-service helm/patient-service \
  --namespace dev \
  -f helm/patient-service/values-local.yaml

helm upgrade --install appointment-service helm/appointment-service \
  --namespace dev \
  -f helm/appointment-service/values-local.yaml

helm upgrade --install audit-service helm/audit-service \
  --namespace dev \
  -f helm/audit-service/values-local.yaml

helm upgrade --install notification-service helm/notification-service \
  --namespace dev \
  -f helm/notification-service/values-local.yaml
```

Watch all pods start:
```bash
kubectl get pods -n dev -w
```

---

## Step 8 — Check Helm release list

```bash
helm list -n dev
```

You should see 4 releases + postgresql, all with STATUS `deployed`.

---

## Step 9 — Practice helm upgrade

Change patient-service to 2 replicas without touching YAML files:

```bash
helm upgrade patient-service helm/patient-service \
  --namespace dev \
  -f helm/patient-service/values-local.yaml \
  --set replicaCount=2

kubectl get pods -n dev -l app=patient-service
```

You should see 2 patient-service pods.

---

## Step 10 — Practice helm rollback

```bash
# See the history of patient-service releases
helm history patient-service -n dev

# Roll back to revision 1 (before we set replicas=2)
helm rollback patient-service 1 -n dev

# Should be back to 1 pod
kubectl get pods -n dev -l app=patient-service
```

**This is how you recover from a bad deployment in production.**
In cloud-care-k8s, if a new image breaks prod, you run `helm rollback <service> <revision> -n prod`.

---

## Step 11 — Test the APIs

```bash
# Port-forward patient-service
kubectl port-forward svc/patient-service 8001:8001 -n dev &

# Port-forward appointment-service
kubectl port-forward svc/appointment-service 8002:8002 -n dev &
```

Test:
```bash
# Create a patient
curl -X POST http://localhost:8001/patients \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Jane Doe","date_of_birth":"1990-01-01","phone":"+94771234567"}'

# List patients
curl http://localhost:8001/patients

# Create appointment (use patient id from above)
curl -X POST http://localhost:8002/appointments \
  -H "Content-Type: application/json" \
  -d '{"patient_id":1,"scheduled_for":"2026-07-01T10:00:00","reason":"Checkup","status":"scheduled"}'

# List appointments
curl http://localhost:8002/appointments
```

---

## Key Helm commands reference

| Command | What it does |
|---------|-------------|
| `helm install <name> <chart>` | Install a chart for the first time |
| `helm upgrade <name> <chart>` | Update an existing release |
| `helm upgrade --install <name> <chart>` | Install if not exists, upgrade if exists |
| `helm list -n <ns>` | List all releases in a namespace |
| `helm history <name> -n <ns>` | Show all revisions of a release |
| `helm rollback <name> <revision> -n <ns>` | Roll back to a previous revision |
| `helm uninstall <name> -n <ns>` | Remove a release and all its resources |
| `helm template <name> <chart>` | Preview the generated YAML without applying |
| `helm get values <name> -n <ns>` | See the values used for a release |

---

## Done when
- All 4 services deployed with Helm and showing `deployed` in `helm list`
- You upgraded patient-service to 2 replicas with `--set`
- You rolled it back to 1 replica with `helm rollback`
- You can create a patient and an appointment via curl
