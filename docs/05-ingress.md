# Phase 4 — Ingress: Route Traffic to All Services

## What you learn
- What Ingress is and why `kubectl port-forward` doesn't scale
- NGINX Ingress Controller (already installed as minikube addon)
- Write Ingress rules to route by URL path
- Use `minikube tunnel` to expose Ingress to your laptop
- Test all 4 services through a single entry point

---

## The problem with port-forward

In Phase 2 and Phase 3 you used `kubectl port-forward` to access services.
That works for one service at a time, but in real life:

- You have 4 services — you'd need 4 separate port-forwards running
- Each time a pod restarts, the port-forward drops
- There's no URL routing — you have to remember which port is which service

**Ingress solves this.** One entry point, route by URL path:

```
http://localhost/patients        → patient-service:8001
http://localhost/appointments    → appointment-service:8002
http://localhost/audit           → audit-service:8003
http://localhost/notifications   → notification-service:8004
```

---

## How it works

```
Your laptop
    │
    │  http://localhost/patients
    ▼
[ minikube tunnel ]
    │
    ▼
[ NGINX Ingress Controller ]  ← already installed (minikube addon)
    │
    ├──  /patients         →  patient-service:8001
    ├──  /appointments     →  appointment-service:8002
    ├──  /audit            →  audit-service:8003
    └──  /notifications    →  notification-service:8004
```

---

## Step 1 — Make sure all 4 services are running

Before setting up Ingress, all 4 services must be deployed (from Phase 3 Helm).
Check:

```bash
kubectl get pods -n dev
kubectl get svc -n dev
```

You should see pods for patient-service, appointment-service, audit-service,
notification-service, and postgresql. All `1/1 Running`.

If any are missing, go back to Phase 3 and deploy them first.

---

## Step 2 — Verify the Ingress controller is running

minikube's `ingress` addon installs NGINX Ingress Controller automatically.

```bash
kubectl get pods -n ingress-nginx
```

You should see something like:
```
ingress-nginx-controller-xxx   1/1   Running   0   ...
```

If it shows `0/1` or is missing, re-enable the addon:
```bash
minikube addons enable ingress
```

---

## Step 3 — Understand an Ingress resource

An Ingress is a Kubernetes object that tells the NGINX controller how to route traffic.

Here's a simple example (don't apply this yet):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example
spec:
  rules:
    - http:
        paths:
          - path: /patients
            pathType: Prefix
            backend:
              service:
                name: patient-service
                port:
                  number: 8001
```

**What each field means:**
- `pathType: Prefix` — any URL starting with `/patients` matches (e.g. `/patients/1`, `/patients?page=2`)
- `backend.service.name` — the Kubernetes Service to forward to
- `backend.service.port.number` — the port on that Service

---

## Step 4 — Write the Ingress resource for all 4 services

Create `k8s/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cloudcare-ingress
  namespace: dev
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx
  rules:
    - http:
        paths:
          - path: /patients(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: patient-service
                port:
                  number: 8001
          - path: /appointments(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: appointment-service
                port:
                  number: 8002
          - path: /audit(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: audit-service
                port:
                  number: 8003
          - path: /notifications(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service:
                name: notification-service
                port:
                  number: 8004
```

**The `rewrite-target` annotation explained:**

Without it: `GET /patients/1` reaches patient-service as `GET /patients/1`
— but patient-service expects `GET /1` (it doesn't know about the `/patients` prefix).

With `rewrite-target: /$2` and the regex path `(/|$)(.*)`:
- `$2` captures everything after `/patients`
- `/patients/1` → arrives at patient-service as `/1` ✓
- `/patients` → arrives as `/` (the list endpoint) ✓

This is the same pattern used in the cloud-care-k8s ALB.

---

## Step 5 — Apply the Ingress

```bash
kubectl apply -f k8s/ingress.yaml
```

Check it was created:
```bash
kubectl get ingress -n dev
```

You'll see something like:
```
NAME                 CLASS   HOSTS   ADDRESS        PORTS   AGE
cloudcare-ingress    nginx   *       192.168.49.2   80      10s
```

The ADDRESS is the minikube cluster IP — not yet reachable from your laptop.

---

## Step 6 — Start minikube tunnel

`minikube tunnel` bridges the minikube cluster IP to your laptop's `localhost`.
It needs to run in a **separate terminal** and stay open while you work.

Open a new terminal and run:
```bash
minikube tunnel
```

It will ask for your sudo password (it modifies routing rules).
Leave this terminal open — don't close it.

---

## Step 7 — Test all services through Ingress

Back in your main terminal (stop any existing port-forwards first with Ctrl+C):

```bash
# Health checks
curl http://localhost/patients/health
curl http://localhost/appointments/health
curl http://localhost/audit/health
curl http://localhost/notifications/health
```

All should return `{"status": "ok", ...}`.

```bash
# Create a patient
curl -X POST http://localhost/patients/patients \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Alice Smith","date_of_birth":"1988-03-15","phone":"+94771111111"}'

# List patients
curl http://localhost/patients/patients

# Book an appointment (use id from above)
curl -X POST http://localhost/appointments/appointments \
  -H "Content-Type: application/json" \
  -d '{"patient_id":1,"scheduled_for":"2026-08-01T10:00:00","reason":"Annual checkup","status":"scheduled"}'

# List appointments
curl http://localhost/appointments/appointments
```

---

## Step 8 — Inspect how NGINX sees the routing

```bash
# See the NGINX config that Ingress generated
kubectl exec -n ingress-nginx \
  $(kubectl get pods -n ingress-nginx -o jsonpath='{.items[0].metadata.name}') \
  -- cat /etc/nginx/nginx.conf | grep -A5 "patient-service"
```

You'll see NGINX upstream blocks pointing to your service ClusterIPs.
This is how the abstraction works — the Ingress controller translated your
Ingress YAML into a real NGINX config file.

---

## Step 9 — Simulate Ingress routing a 404

What happens when no path matches?

```bash
curl -v http://localhost/unknown-path
```

You'll get a `404 Not Found` from NGINX itself, not from your services.
NGINX handles it before the request reaches any pod.

---

## Step 10 — Update the doc knowledge: cloud-care-k8s comparison

In **cloud-care-k8s** the same concept was done with:
- `aws-load-balancer-controller` (instead of NGINX Ingress)
- `Ingress` with `kubernetes.io/ingress.class: alb` annotation (instead of `nginx`)
- ALB created a real AWS load balancer with a public DNS name

The Ingress YAML structure is almost identical. Only the annotations and
ingress class change between cloud providers.

---

## Key concepts learned

| Concept | What it means |
|---------|--------------|
| Ingress | Kubernetes object that defines URL routing rules |
| Ingress Controller | The actual software that reads Ingress rules and routes traffic (NGINX here) |
| `pathType: Prefix` | Match any URL that starts with the given path |
| `rewrite-target` | Strip the path prefix before forwarding to the backend service |
| `minikube tunnel` | Expose the cluster's LoadBalancer IP to localhost |
| `ingressClassName` | Tells Kubernetes which Ingress Controller to use |

---

## Done when
- `kubectl get ingress -n dev` shows an ADDRESS
- `minikube tunnel` is running in a separate terminal
- All 4 health endpoints respond through `http://localhost/<service>/health`
- You can create a patient and list patients through `http://localhost/patients/patients`
