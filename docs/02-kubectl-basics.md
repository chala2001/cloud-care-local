# Phase 1 — Deploy First Service with Raw kubectl

## Why this phase exists
In cloud-care-k8s we used Helm from the start. Helm generates YAML and applies it for you.
But if you don't understand the raw YAML, you can't debug when Helm fails.
This phase: write YAML by hand → understand every field → then Helm in Phase 3 makes sense.

We deploy ONLY patient-service here. No database yet — we use a fake in-memory response
just to get the pod running and understand kubectl.

---

## What we're building

```
Your terminal
     │
     │  kubectl port-forward
     ▼
[ patient-service pod ]  ← runs inside minikube
      port 8001
```

No ingress yet. No database. Just a running pod you can talk to.

---

## Step 1 — Create a namespace

A namespace is like a folder inside Kubernetes. It keeps resources organized.

```bash
kubectl create namespace dev
```

Verify:
```bash
kubectl get namespaces
```

You should see `dev` in the list alongside `default`, `kube-system` etc.

---

## Step 2 — Write the Deployment YAML

Create this file at `k8s/patient-service-deployment.yaml`:

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
          image: python:3.12-slim
          command: ["python", "-m", "http.server", "8001"]
          ports:
            - containerPort: 8001
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "200m"
              memory: "256Mi"
```

**What each section means:**
- `replicas: 1` — run 1 pod
- `selector.matchLabels` — the Deployment finds its pods by this label
- `template.labels` — every pod gets this label (must match selector)
- `image: python:3.12-slim` — using a simple Python image (no need to build anything yet)
- `command` — starts Python's built-in HTTP server on port 8001
- `resources.requests` — minimum CPU/RAM the pod needs (scheduler uses this)
- `resources.limits` — maximum CPU/RAM the pod can use (enforced by kernel)

---

## Step 3 — Apply the Deployment

```bash
mkdir -p k8s
kubectl apply -f k8s/patient-service-deployment.yaml
```

Watch the pod start:
```bash
kubectl get pods -n dev -w
```

You should see:
```
NAME                               READY   STATUS              RESTARTS   AGE
patient-service-xxx-xxx            0/1     ContainerCreating   0          2s
patient-service-xxx-xxx            1/1     Running             0          8s
```

Press `Ctrl+C` to stop watching.

---

## Step 4 — Explore the running pod

```bash
# See pod details — events, IP, node, image
kubectl describe pod -n dev -l app=patient-service

# See logs from the container
kubectl logs -n dev -l app=patient-service

# Get inside the running container (like SSH)
kubectl exec -it -n dev deployment/patient-service -- bash
```

Once inside the container, run:
```bash
curl localhost:8001
exit
```

You'll see the Python HTTP server response. You're inside a running Kubernetes pod.

---

## Step 5 — Write the Service YAML

A Service gives the pod a stable internal DNS name. Without it, pods can only be reached
by their IP — which changes every time the pod restarts.

Create `k8s/patient-service-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: patient-service
  namespace: dev
spec:
  selector:
    app: patient-service
  ports:
    - port: 8001
      targetPort: 8001
  type: ClusterIP
```

**What each section means:**
- `selector.app: patient-service` — routes traffic to pods with this label
- `port: 8001` — the port the Service listens on inside the cluster
- `targetPort: 8001` — the port on the pod to forward to
- `type: ClusterIP` — only reachable from inside the cluster (not from internet)

Apply it:
```bash
kubectl apply -f k8s/patient-service-service.yaml
```

Verify:
```bash
kubectl get service -n dev
```

---

## Step 6 — Access from your laptop via port-forward

`kubectl port-forward` tunnels a port from your laptop into the cluster:

```bash
kubectl port-forward svc/patient-service 8001:8001 -n dev
```

Now in **another terminal**:
```bash
curl http://localhost:8001
```

You should get a response from the Python HTTP server inside the pod.

Press `Ctrl+C` to stop the port-forward.

---

## Step 7 — Scale up and down

```bash
# Scale to 3 replicas
kubectl scale deployment patient-service -n dev --replicas=3

# Watch 3 pods come up
kubectl get pods -n dev -w

# Scale back to 1
kubectl scale deployment patient-service -n dev --replicas=1
```

Notice: when you scale down, Kubernetes picks which pods to terminate. You don't choose.

---

## Step 8 — Simulate a crash and watch self-healing

```bash
# Delete a pod manually
kubectl delete pod -n dev -l app=patient-service

# Immediately watch — Kubernetes creates a new one automatically
kubectl get pods -n dev -w
```

This is self-healing. The Deployment controller sees "I need 1 replica, I have 0" and
creates a new pod immediately. This is why you never manage pods directly — you manage
Deployments.

---

## Step 9 — Clean up

```bash
kubectl delete -f k8s/patient-service-deployment.yaml
kubectl delete -f k8s/patient-service-service.yaml
```

Verify everything is gone:
```bash
kubectl get all -n dev
```

---

## Key kubectl commands learned

| Command | What it does |
|---------|-------------|
| `kubectl apply -f <file>` | Create or update resources from YAML |
| `kubectl get pods -n <ns>` | List pods in a namespace |
| `kubectl get pods -n <ns> -w` | Watch pods in real time |
| `kubectl describe pod <name> -n <ns>` | Full details + events (use when pod fails) |
| `kubectl logs <pod> -n <ns>` | See container stdout |
| `kubectl exec -it <pod> -n <ns> -- bash` | Get a shell inside the container |
| `kubectl scale deployment <name> -n <ns> --replicas=N` | Scale up/down |
| `kubectl delete -f <file>` | Delete resources defined in YAML |
| `kubectl port-forward svc/<name> <local>:<remote> -n <ns>` | Tunnel to your laptop |

---

## Done when
- You ran a pod, got inside it with exec, curled it from your laptop via port-forward
- You scaled it up and down
- You deleted a pod and watched Kubernetes recreate it automatically
- You cleaned up and `kubectl get all -n dev` shows nothing
