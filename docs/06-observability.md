# Phase 5 — Observability: Prometheus, Grafana, and Loki

## What you learn
- Install the full monitoring stack with Helm (Prometheus + Grafana + AlertManager)
- Install Loki + Promtail for log aggregation
- Write PromQL queries to explore metrics
- Build a Grafana dashboard for your services
- Set up an alert rule
- Understand the difference between metrics (Prometheus) and logs (Loki)

---

## What you're building

```
[ patient-service ]  ──scrape /metrics──▶  [ Prometheus ]
[ appointment-service ] ─────────────────▶  [ Prometheus ]
[ audit-service ]       ─────────────────▶  [ Prometheus ]
[ notification-service ]─────────────────▶  [ Prometheus ]

[ Promtail ] ─── collects container logs ──▶ [ Loki ]

[ Grafana ] ─── queries ──▶ Prometheus  (metrics dashboards)
              ─── queries ──▶ Loki       (log explorer)
```

In **cloud-care-k8s** you already set this up on EKS.
Here we do exactly the same thing on minikube — same Helm charts, same PromQL,
same dashboards. The only difference is the cluster is local.

---

## Step 1 — Add Helm repos

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

Verify:
```bash
helm search repo prometheus-community/kube-prometheus-stack
helm search repo grafana/loki-stack
```

---

## Step 2 — Create the monitoring namespace

```bash
kubectl create namespace monitoring
```

---

## Step 3 — Copy monitoring values from cloud-care-k8s

The Prometheus and Loki values files already exist from cloud-care-k8s.
Copy them:

```bash
cp -r /home/chalaka/cloud-care-both/cloud-care-k8s/monitoring \
      /home/chalaka/cloud-care-both/cloud-care-local/
```

Verify:
```bash
ls monitoring/
# prometheus/  loki/
ls monitoring/prometheus/
# values.yaml  alerts.yaml
```

---

## Step 4 — Review the Prometheus values

```bash
cat monitoring/prometheus/values.yaml
```

Key settings to notice:
- `grafana.adminPassword` — the Grafana login password
- `prometheus.prometheusSpec.scrapeInterval` — how often Prometheus scrapes metrics
- `alertmanager` section — where alerts go (we'll use it later)

You don't need to change anything — these values work for local too.

---

## Step 5 — Install kube-prometheus-stack

This single Helm chart installs Prometheus + Grafana + AlertManager + node exporters:

```bash
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values monitoring/prometheus/values.yaml \
  --timeout 10m
```

This takes 3-5 minutes. Watch pods start:

```bash
kubectl get pods -n monitoring -w
```

Wait until all pods are `1/1 Running`. Press `Ctrl+C` when done.

Expected pods:
```
alertmanager-kube-prometheus-stack-alertmanager-0   2/2   Running
kube-prometheus-stack-grafana-xxx                   3/3   Running
kube-prometheus-stack-kube-state-metrics-xxx        1/1   Running
kube-prometheus-stack-operator-xxx                  1/1   Running
kube-prometheus-stack-prometheus-node-exporter-xxx  1/1   Running
prometheus-kube-prometheus-stack-prometheus-0       2/2   Running
```

---

## Step 6 — Install Loki + Promtail

Loki stores logs. Promtail runs on each node and ships container logs to Loki.

```bash
helm upgrade --install loki-stack grafana/loki-stack \
  --namespace monitoring \
  --values monitoring/loki/values.yaml \
  --timeout 5m
```

Check:
```bash
kubectl get pods -n monitoring | grep loki
```

You should see `loki-stack-0` and `loki-stack-promtail-xxx` both `Running`.

---

## Step 7 — Open Grafana

Port-forward Grafana to your laptop:

```bash
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring
```

Open your browser: **http://localhost:3000**

Login:
- **Username:** `admin`
- **Password:** check your `monitoring/prometheus/values.yaml` for `grafana.adminPassword`
  (in cloud-care-k8s it was `cloudcare-grafana`)

---

## Step 8 — Explore pre-built dashboards

Grafana comes with dashboards already installed by kube-prometheus-stack.

In Grafana left sidebar → **Dashboards** → Browse:

- **Kubernetes / Compute Resources / Namespace (Pods)** — CPU and RAM per pod
- **Kubernetes / Compute Resources / Cluster** — whole cluster overview
- **Node Exporter / Nodes** — host-level metrics (CPU, disk, network)

Click into **Kubernetes / Compute Resources / Namespace (Pods)**.
Change the namespace dropdown to `dev`.
You'll see CPU and memory graphs for your 4 services and postgresql.

---

## Step 9 — Add Loki as a data source

Grafana needs to know where Loki is. Check if it's already added:

Left sidebar → **Connections** → **Data Sources**

If you see Loki listed, skip to Step 10.

If not, add it:
1. Click **Add data source**
2. Choose **Loki**
3. URL: `http://loki-stack:3100`
4. Click **Save & Test** — should say "Data source connected"

---

## Step 10 — Explore logs in Grafana

Left sidebar → **Explore**

At the top, select **Loki** as the data source.

Click **Label filters** and add:
- Label: `namespace`
- Value: `dev`

Click **Run query**. You'll see log lines from all 4 services streaming in.

Filter to one service:
- Add another label filter: `app = patient-service`

Now run some API requests to generate logs:
```bash
curl -X POST http://localhost/patients/patients \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Bob Lee","date_of_birth":"1992-06-20","phone":"+94779999999"}'

curl http://localhost/patients/patients
```

Switch back to Grafana — you'll see the log lines from those requests appear in real time.

---

## Step 11 — Write PromQL queries

Left sidebar → **Explore** → switch data source to **Prometheus**

Try these queries one by one — type each in the query box and click **Run query**:

**Are all services up?**
```promql
up{namespace="dev"}
```
Should return a `1` for each service. A `0` means Prometheus can't reach that service's `/metrics` endpoint.

**HTTP request rate over last 5 minutes:**
```promql
rate(http_requests_total{namespace="dev"}[5m])
```
Shows requests per second per service. Generate some traffic with curl and watch the values change.

**Memory usage per pod:**
```promql
container_memory_working_set_bytes{namespace="dev", container!=""}
```
Shows actual RAM used by each container.

**CPU usage per pod:**
```promql
rate(container_cpu_usage_seconds_total{namespace="dev", container!=""}[5m])
```

---

## Step 12 — Build a custom dashboard

1. Left sidebar → **Dashboards** → **New** → **New Dashboard**
2. Click **Add visualization**
3. Data source: **Prometheus**
4. Query:
   ```promql
   rate(http_requests_total{namespace="dev"}[5m])
   ```
5. Legend: `{{pod}}`
6. Panel title: `Request Rate — dev namespace`
7. Click **Apply**

Add a second panel:
1. Click **Add** → **Visualization**
2. Query:
   ```promql
   up{namespace="dev"}
   ```
3. Visualization type: **Stat** (top right dropdown)
4. Panel title: `Services Up`
5. Click **Apply**

Save the dashboard: top right → **Save dashboard** → name it `CloudCare Local`

---

## Step 13 — Create an alert rule

Alerts fire when something goes wrong — like a service going down.

Left sidebar → **Alerting** → **Alert rules** → **New alert rule**

Fill in:
- **Rule name:** `Patient Service Down`
- **Query A:**
  ```promql
  up{job="patient-service", namespace="dev"}
  ```
- **Condition:** IS BELOW `1`
- **Evaluate every:** `1m` for `2m`
  (fires if service is down for 2 consecutive minutes)
- **Folder:** General
- **Save**

To test it: scale patient-service to 0 replicas:

```bash
kubectl scale deployment patient-service -n dev --replicas=0
```

Wait 2 minutes, then check Alerting → Alert rules — the rule should show as **Firing**.

Scale back up:
```bash
kubectl scale deployment patient-service -n dev --replicas=1
```

---

## Step 14 — Check what ServiceMonitor does

`kube-prometheus-stack` uses a custom resource called `ServiceMonitor` to tell Prometheus
which services to scrape. Check if your services have one:

```bash
kubectl get servicemonitor -n dev
```

If empty, Prometheus won't scrape your services. Check if the chart created them,
or if `up{namespace="dev"}` in PromQL returns results.

If no results, you may need to add annotations to your services so Prometheus
discovers them via pod annotations instead:

```bash
kubectl annotate svc patient-service -n dev \
  prometheus.io/scrape="true" \
  prometheus.io/port="8001" \
  prometheus.io/path="/metrics"
```

Then wait 30 seconds and run `up{namespace="dev"}` again in Grafana Explore.

---

## Step 15 — Compare with cloud-care-k8s

Everything you just did is identical to what ran on EKS, except:

| Thing | cloud-care-k8s | cloud-care-local |
|-------|---------------|-----------------|
| Cluster | EKS | minikube |
| Grafana access | ALB URL + Route53 | `kubectl port-forward` |
| Persistent storage | AWS EBS PVC | minikube hostpath PVC |
| Alerting destination | CloudWatch / email | Grafana UI only |
| Promtail target | EKS node logs | minikube Docker logs |

The PromQL queries, dashboards, and alert rules are **100% identical**.
This is the power of Kubernetes — the observability layer is portable.

---

## Key concepts learned

| Concept | What it means |
|---------|--------------|
| Prometheus | Time-series metrics database — scrapes `/metrics` from each service |
| PromQL | Prometheus query language — used to build graphs and alerts |
| Grafana | Dashboard and alerting UI — queries Prometheus and Loki |
| Loki | Log aggregation — stores and indexes container logs |
| Promtail | Log shipper — runs on each node, collects and forwards logs to Loki |
| AlertManager | Handles alert routing — sends notifications when Prometheus rules fire |
| ServiceMonitor | CRD that tells Prometheus which services to scrape |
| `up{}` | Core Prometheus metric — 1 = service reachable, 0 = down |

---

## Done when
- `kubectl get pods -n monitoring` shows all pods Running
- You can open Grafana at `http://localhost:3000` and see dashboards
- `up{namespace="dev"}` in Prometheus Explore returns results for your services
- You can see live logs from patient-service in Loki Explore
- You built at least one custom dashboard panel
- You created an alert rule and watched it fire when you scaled patient-service to 0
