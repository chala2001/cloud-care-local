# Phase 0 — Setup

## What you have
- Docker 29.1.3 ✅
- kubectl v1.36.0 ✅
- Helm v3.20.2 ✅
- minikube v1.38.1 ✅

No installation needed. Jump straight to starting minikube.

---

## Start minikube

```bash
minikube start --cpus=4 --memory=4096 --driver=docker
```

**What each flag means:**
- `--cpus=4` — give minikube 4 CPU cores (monitoring stack needs it)
- `--memory=4096` — 4GB RAM (Prometheus + Grafana + 4 services need this)
- `--driver=docker` — runs minikube as a Docker container (no VM needed)

This takes 2-3 minutes the first time (downloads the minikube base image).

---

## Enable required addons

```bash
# Ingress controller (nginx) — routes external traffic into the cluster
minikube addons enable ingress

# Metrics server — required for HPA to read CPU usage
minikube addons enable metrics-server
```

---

## Verify everything is running

```bash
# Should show 1 node in Ready state
kubectl get nodes

# Should show all system pods Running
kubectl get pods -n kube-system

# Should show ingress-nginx pods
kubectl get pods -n ingress-nginx
```

---

## Useful minikube commands (reference)

```bash
minikube status          # is the cluster running?
minikube stop            # pause the cluster (saves RAM)
minikube start           # resume it
minikube delete          # wipe everything and start fresh
minikube dashboard       # open Kubernetes web UI in browser
minikube tunnel          # expose LoadBalancer/Ingress to localhost (run in separate terminal)
minikube ip              # get the cluster IP
```

---

## Done when
- `kubectl get nodes` shows `minikube   Ready`
- `kubectl get pods -n kube-system` shows all pods Running
