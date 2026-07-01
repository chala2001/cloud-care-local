# Phase 4 — Ingress: Route Traffic to All Services

## What you learn
- What Ingress is and why `kubectl port-forward` per service doesn't scale
- NGINX Ingress Controller (already installed as minikube addon)
- Write Ingress rules to route by URL path
- Access all 4 services through a single entry point on port 8080

---

## The problem with port-forward per service

In Phase 2 and Phase 3 you used `kubectl port-forward` to access services.
That works for one service at a time, but in real life:

- You have 4 services — you'd need 4 separate port-forwards running in 4 terminals
- Each time a pod restarts, the port-forward drops
- There's no URL routing — you have to remember which port is which service

**Ingress solves this.** One entry point, route by URL path:

```
http://localhost:8080/patients        → patient-service:8001
http://localhost:8080/appointments    → appointment-service:8002
http://localhost:8080/audit           → audit-service:8003
http://localhost:8080/notifications   → notification-service:8004
```

---

## How it works on minikube

```
Your laptop
    │
    │  http://localhost:8080/patients
    ▼
[ kubectl port-forward → ingress-nginx-controller:80 ]
    │
    ▼
[ NGINX Ingress Controller ]  ← already installed (minikube addon)
    │
    ├──  /patients         →  patient-service:8001
    ├──  /appointments     →  appointment-service:8002
    ├──  /audit            →  audit-service:8003
    └──  /notifications    →  notification-service:8004
```

**Why port 8080 and not 80?**
On Linux, binding to ports below 1024 requires root. Port 80 gives
`permission denied`. We port-forward the ingress controller to localhost:8080
instead — functionally identical, just a different port number.

---

## Step 1 — Make sure all 4 services are running

```bash
kubectl get pods -n dev
kubectl get svc -n dev
```

You should see patient-service, appointment-service, audit-service,
notification-service, and postgresql — all `1/1 Running`.

If any are missing, go back to Phase 3 and deploy them first.

---

## Step 2 — Verify the Ingress controller is running

minikube's `ingress` addon installs NGINX Ingress Controller automatically.

```bash
kubectl get pods -n ingress-nginx
```

You should see:
```
ingress-nginx-controller-xxx   1/1   Running   ...
```

Also check its service type — on minikube it's NodePort (not LoadBalancer):
```bash
kubectl get svc -n ingress-nginx
```

```
NAME                       TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)
ingress-nginx-controller   NodePort   10.96.x.x      <none>        80:3xxxx/TCP
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
- `pathType: Prefix` — any URL starting with `/patients` matches (`/patients/1`, `/patients?page=2`)
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

Without it: `GET /patients/1` arrives at patient-service as `GET /patients/1`
— but patient-service expects `GET /1` (it doesn't know about the `/patients` prefix).

With `rewrite-target: /$2` and the regex path `(/|$)(.*)`:
- `$2` captures everything after `/patients`
- `/patients/1` → arrives at patient-service as `/1` ✓
- `/patients` → arrives as `/` (the list endpoint) ✓

---

## Step 5 — Apply the Ingress

```bash
kubectl apply -f k8s/ingress.yaml
```

Check it was created:
```bash
kubectl get ingress -n dev
```

```
NAME                CLASS   HOSTS   ADDRESS   PORTS   AGE
cloudcare-ingress   nginx   *                 80      10s
```

The ADDRESS may be empty — that's fine on minikube with NodePort. It doesn't affect routing.

---

## Step 6 — Port-forward the Ingress controller to localhost:8080

Open a **new terminal** and run this — keep it open while you work:

```bash
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80
```

You'll see:
```
Forwarding from 127.0.0.1:8080 -> 80
Forwarding from [::1]:8080 -> 80
```

This tunnels your laptop's port 8080 into the NGINX controller's port 80.
All Ingress routing happens inside the cluster from there.

---

## Step 7 — Test all services through Ingress

In your main terminal:

```bash
# Health checks — all should return {"status": "ok", ...}
curl http://localhost:8080/patients/health
curl http://localhost:8080/appointments/health
curl http://localhost:8080/audit/health
curl http://localhost:8080/notifications/health
```

```bash
# Create a patient
curl -X POST http://localhost:8080/patients/patients \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Alice Smith","date_of_birth":"1988-03-15","phone":"+94771111111"}'

# List patients
curl http://localhost:8080/patients/patients

# Book an appointment (use patient id from above)
curl -X POST http://localhost:8080/appointments/appointments \
  -H "Content-Type: application/json" \
  -d '{"patient_id":1,"scheduled_for":"2026-08-01T10:00:00","reason":"Annual checkup","status":"scheduled"}'

# List appointments
curl http://localhost:8080/appointments/appointments
```

---

## Step 8 — Inspect how NGINX sees the routing

```bash
kubectl exec -n ingress-nginx \
  $(kubectl get pods -n ingress-nginx -o jsonpath='{.items[0].metadata.name}') \
  -- cat /etc/nginx/nginx.conf | grep -A5 "patient-service"
```

You'll see NGINX upstream blocks pointing to your service ClusterIPs.
The Ingress controller translated your Ingress YAML into a real NGINX config file.

---

## Step 9 — Simulate a 404 from NGINX

What happens when no path matches?

```bash
curl -v http://localhost:8080/unknown-path
```

You'll get `404 Not Found` from NGINX itself — before the request reaches any pod.

---

## Step 10 — cloud-care-k8s comparison

In **cloud-care-k8s** the same concept used:
- `aws-load-balancer-controller` instead of NGINX
- `Ingress` with `kubernetes.io/ingress.class: alb` instead of `nginx`
- ALB created a real AWS load balancer with a public DNS name — no port-forward needed

The Ingress YAML structure is almost identical. Only the annotations and ingress class change.

| | cloud-care-k8s | cloud-care-local |
|-|---------------|-----------------|
| Controller | AWS ALB Controller | NGINX (minikube addon) |
| Service type | LoadBalancer (real AWS ALB) | NodePort |
| Access | Public ALB DNS hostname | `localhost:8080` via port-forward |
| TLS | ACM certificate | None (local only) |

---

## Key concepts learned

| Concept | What it means |
|---------|--------------|
| Ingress | Kubernetes object that defines URL routing rules |
| Ingress Controller | Software that reads Ingress rules and routes traffic (NGINX here) |
| `rewrite-target` | Strip the path prefix before forwarding to the backend |
| `pathType: ImplementationSpecific` | Allows regex paths with capture groups |
| NodePort | Service type that exposes on a random high port on the node |
| Port 8080 | Used instead of 80 because port 80 requires root on Linux |

---

## Known issue — port 80 permission denied

Running `kubectl port-forward ... 80:80` on Linux gives:
```
unable to create listener: Error listen tcp4 127.0.0.1:80: bind: permission denied
```

**Fix:** Use port 8080 instead: `kubectl port-forward ... 8080:80`
Then access all services via `http://localhost:8080/...` instead of `http://localhost/...`.

---

## Done when
- `kubectl get ingress -n dev` shows `cloudcare-ingress`
- `kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80` is running
- All 4 health endpoints respond on `http://localhost:8080/<service>/health`
- You can create a patient and list patients through `http://localhost:8080/patients/patients`
