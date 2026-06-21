# Phase 2 — Database Inside Kubernetes

## What you learn
- Run PostgreSQL as a pod using Helm (bitnami chart)
- Create Kubernetes Secrets for DB credentials
- Connect patient-service to PostgreSQL
- Use `kubectl exec` to run psql commands inside the DB pod
- Understand PersistentVolumeClaims — how data survives pod restarts

---

## What we're building

```
Your laptop
     │
     │  kubectl port-forward
     ▼
[ patient-service pod ]  ←→  [ postgresql pod ]
     port 8001                    port 5432
                                      │
                                 [ PVC — data lives here ]
```

---

## Step 1 — Add the Bitnami Helm repo

Bitnami provides production-ready Helm charts for common databases.

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
```

Verify:
```bash
helm search repo bitnami/postgresql
```

You should see the postgresql chart listed with a version number.

---

## Step 2 — Install PostgreSQL with Helm

```bash
helm upgrade --install postgresql bitnami/postgresql \
  --namespace dev \
  --set auth.username=patient_svc \
  --set auth.password=devpassword123 \
  --set auth.database=cloudcare \
  --set primary.persistence.size=1Gi
```

**What each flag means:**
- `auth.username` — creates a DB user called `patient_svc`
- `auth.password` — password for that user
- `auth.database` — creates a database called `cloudcare`
- `primary.persistence.size=1Gi` — 1GB disk for data storage (PVC)

Watch it start:
```bash
kubectl get pods -n dev -w
```

Wait until `postgresql-0` shows `1/1 Running`. Press `Ctrl+C`.

---

## Step 3 — Understand what was created

```bash
kubectl get all -n dev
kubectl get pvc -n dev
```

You'll see:
- `pod/postgresql-0` — the database pod (StatefulSet, not Deployment)
- `svc/postgresql` — ClusterIP service on port 5432
- `pvc/data-postgresql-0` — the persistent disk (data survives pod restarts)

**Why StatefulSet and not Deployment?**
Deployments are for stateless apps — any pod is interchangeable.
StatefulSets are for stateful apps (databases) — each pod has a fixed identity
and its own persistent storage. `postgresql-0` always gets the same PVC.

---

## Step 4 — Connect to PostgreSQL directly

```bash
kubectl exec -it postgresql-0 -n dev -- psql \
  -U patient_svc -d cloudcare
```

Once inside psql:
```sql
-- See all tables (empty for now)
\dt

-- Create a test table
CREATE TABLE test (id serial PRIMARY KEY, name text);
INSERT INTO test (name) VALUES ('hello from kubernetes');
SELECT * FROM test;

-- Exit
\q
```

You just ran SQL commands inside a Kubernetes pod against a PostgreSQL database
that is running inside the cluster.

---

## Step 5 — Create a Kubernetes Secret for the DB credentials

Never put passwords in Deployment YAML directly. Store them in a Secret.

```bash
kubectl create secret generic patient-service-db-secret \
  --from-literal=DATABASE_URL="postgresql://patient_svc:devpassword123@postgresql:5432/cloudcare" \
  --namespace dev
```

Verify:
```bash
kubectl get secret patient-service-db-secret -n dev
kubectl describe secret patient-service-db-secret -n dev
```

Notice: the value is base64-encoded — not plaintext, but not encrypted either.
Kubernetes Secrets are just base64 by default. In production (cloud-care-k8s)
we used AWS Secrets Manager. Here base64 is fine for local dev.

---

## Step 6 — Build the patient-service Docker image into minikube

minikube has its own Docker daemon. We need to build the image there so Kubernetes
can use it without pushing to a registry.

```bash
# Point your terminal's docker command to minikube's docker daemon
eval $(minikube docker-env)

# Build patient-service image directly into minikube
docker build -t patient-service:local ./services/patient-service

# Verify the image is inside minikube
docker images | grep patient-service
```

**Important:** `eval $(minikube docker-env)` only affects the current terminal session.
Open a new terminal and docker commands go to your normal Docker again.

---

## Step 7 — Write a Deployment that uses the real image + Secret

Create `k8s/patient-service-deployment.yaml` (replace the old one):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: patient-service
  namespace: dev
spec:
  replicas: 1
  selector:
    matchLabels:
      app: patient-service
  template:
    metadata:
      labels:
        app: patient-service
    spec:
      containers:
        - name: patient-service
          image: patient-service:local
          imagePullPolicy: Never        # use local image, don't pull from registry
          ports:
            - containerPort: 8001
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: patient-service-db-secret
                  key: DATABASE_URL
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
```

**Key things:**
- `imagePullPolicy: Never` — use the locally built image, never pull from internet
- `secretKeyRef` — reads DATABASE_URL from the Secret we created in Step 5
  The pod never sees the password in plain YAML — it comes from the Secret at runtime

---

## Step 8 — Apply and verify

```bash
kubectl apply -f k8s/patient-service-deployment.yaml
kubectl apply -f k8s/patient-service-service.yaml

# Watch the pod start
kubectl get pods -n dev -w
```

If the pod crashes, check logs:
```bash
kubectl logs -n dev -l app=patient-service
kubectl describe pod -n dev -l app=patient-service
```

---

## Step 9 — Test the API

```bash
# Port-forward patient-service
kubectl port-forward svc/patient-service 8001:8001 -n dev
```

In another terminal:
```bash
# Check health
curl http://localhost:8001/health

# Create a patient
curl -X POST http://localhost:8001/patients \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Jane Doe","date_of_birth":"1990-01-01","phone":"+94771234567"}'

# List patients
curl http://localhost:8001/patients
```

You should see the patient returned with an `id`. It's stored in PostgreSQL running
inside your minikube cluster.

---

## Step 10 — Prove data persists across pod restarts

```bash
# Create a patient first (if you haven't already)
curl -X POST http://localhost:8001/patients \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Test Patient","date_of_birth":"1985-05-15","phone":"+94777777777"}'

# Delete the patient-service pod (simulates a crash)
kubectl delete pod -n dev -l app=patient-service

# Wait for the new pod to start
kubectl get pods -n dev -w

# Port-forward again to the new pod
kubectl port-forward svc/patient-service 8001:8001 -n dev

# Check — patient is still there (stored in PostgreSQL PVC, not in the pod)
curl http://localhost:8001/patients
```

The patient data survived because it lives in the **PVC** (persistent disk),
not in the pod. The pod is stateless — the database holds the state.

---

## Key concepts learned

| Concept | What it means |
|---------|--------------|
| StatefulSet | Like a Deployment but each pod has a fixed identity + its own PVC |
| PVC (PersistentVolumeClaim) | A request for disk storage — survives pod restarts |
| Secret | Kubernetes object for sensitive data — base64 encoded, not in Git |
| `secretKeyRef` | Inject a Secret value as an env var into a container |
| `imagePullPolicy: Never` | Use locally built image — don't pull from Docker Hub |
| `eval $(minikube docker-env)` | Point docker CLI to minikube's internal Docker daemon |

---

## Done when
- PostgreSQL is running as a pod in the `dev` namespace
- patient-service connects to it and you can create/list patients via curl
- You deleted the pod, it restarted, and the patient data was still there
