# Phase 6 — HPA: Horizontal Pod Autoscaler

## What you learn
- What HPA is and how it decides when to scale
- Enable HPA in your Helm values
- Generate real CPU load with a load test
- Watch pods scale up automatically, then scale back down
- Understand the scale-down delay (cooldown period)

---

## What is HPA?

In cloud-care-k8s you watched patient-service scale from 2 → 6 pods under load,
then slowly back to 2 after the load stopped. That was HPA doing its job.

HPA watches CPU (or memory, or custom metrics) and:
- If CPU > threshold → add more pods
- If CPU < threshold for long enough → remove pods

```
[ HPA controller ]
       │
       │  reads every 15 seconds
       ▼
[ metrics-server ]  ←  collects CPU from each pod
       │
       │  if avg CPU > 70%  →  scale up
       │  if avg CPU < 70%  →  scale down (after cooldown)
       ▼
[ Deployment ]  →  creates/removes pods
```

**metrics-server** is the bridge. It collects CPU from each pod and HPA reads from it.
You enabled it in Phase 0 with `minikube addons enable metrics-server`.

---

## Step 1 — Verify metrics-server is working

```bash
kubectl top pods -n dev
```

You should see CPU and memory numbers for each pod:
```
NAME                               CPU(cores)   MEMORY(bytes)
patient-service-xxx                5m           45Mi
appointment-service-xxx            3m           40Mi
postgresql-0                       10m          120Mi
```

If you get `error: Metrics API not available`, wait 2 more minutes and try again
(metrics-server takes a moment to collect initial data).

---

## Step 2 — Update patient-service Helm values to enable HPA

Open `helm/patient-service/values-local.yaml` and change `hpa.enabled` to `true`:

```yaml
replicaCount: 1

image:
  repository: patient-service
  tag: local
  pullPolicy: Never

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
  enabled: true
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 30   # lower threshold so it's easy to trigger locally

serviceAccount:
  create: false
```

**Why 30% threshold instead of 70%?**
In cloud-care-k8s the threshold was 70% because EKS nodes have real load.
On minikube, your laptop's Docker daemon limits how much CPU the pods can actually use.
30% is easier to trigger so you can observe the scale-up without running a heavy load test.

---

## Step 3 — Apply the updated values

```bash
helm upgrade patient-service helm/patient-service \
  --namespace dev \
  -f helm/patient-service/values-local.yaml
```

Check the HPA was created:
```bash
kubectl get hpa -n dev
```

You should see:
```
NAME              REFERENCE                    TARGETS   MINPODS   MAXPODS   REPLICAS
patient-service   Deployment/patient-service   5%/30%    1         5         1
```

The `TARGETS` column shows current CPU / threshold. It starts low (idle service).

---

## Step 4 — Watch the HPA in one terminal

Open a dedicated terminal and run:

```bash
watch -n 3 kubectl get hpa,pods -n dev
```

This refreshes every 3 seconds. Keep it visible while you run the load test.

---

## Step 5 — Generate load

Make sure `minikube tunnel` is still running (from Phase 4) and Ingress is set up.

Open another terminal and run this load test — it sends 200 concurrent requests
for 3 minutes:

```bash
# Install hey if you don't have it
which hey || go install github.com/rakyll/hey@latest 2>/dev/null || \
  (sudo apt-get install -y hey 2>/dev/null || \
   curl -sf https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64 -o hey && chmod +x hey && sudo mv hey /usr/local/bin/)

# Run the load test
hey -z 180s -c 50 http://localhost/patients/patients
```

If `hey` is not available, use a simple bash loop instead:

```bash
for i in $(seq 1 500); do
  curl -s http://localhost/patients/patients > /dev/null &
done
wait
```

Or with `ab` (Apache Benchmark):
```bash
ab -n 5000 -c 50 http://localhost/patients/patients
```

---

## Step 6 — Watch the scale-up

In your `watch` terminal you'll see the `TARGETS` CPU number climb above 30%.
After about 60-90 seconds the HPA will add more pods:

```
NAME              REFERENCE                    TARGETS    MINPODS   MAXPODS   REPLICAS
patient-service   Deployment/patient-service   45%/30%    1         5         1

# 90 seconds later...

patient-service   Deployment/patient-service   68%/30%    1         5         3

# then...

patient-service   Deployment/patient-service   52%/30%    1         5         4
```

And the pods list will show new patient-service pods starting up.

**How HPA calculates new replica count:**
```
desired replicas = ceil(current replicas × (current CPU% / target CPU%))
                = ceil(1 × (45 / 30))
                = ceil(1.5)
                = 2
```

---

## Step 7 — Stop the load and watch scale-down

Stop the load test (Ctrl+C). Keep watching the HPA.

HPA will NOT scale down immediately. By default it waits **5 minutes** before
scaling down. This prevents flapping — if load spikes again 30 seconds after
scaling down, it would have to scale back up.

You'll see the CPU drop but replicas stay the same:
```
patient-service   Deployment/patient-service   3%/30%    1         5         4
```

After ~5 minutes, it will gradually scale back to 1:
```
patient-service   Deployment/patient-service   2%/30%    1         5         2
# another few minutes...
patient-service   Deployment/patient-service   1%/30%    1         5         1
```

This is exactly what you saw in cloud-care-k8s when you asked "why won't it go back to 2??".
Now you understand why — it's the built-in cooldown.

---

## Step 8 — Inspect the HPA events

```bash
kubectl describe hpa patient-service -n dev
```

Scroll to the **Events** section at the bottom. You'll see the scale-up and scale-down
decisions with timestamps and reasoning:

```
Events:
  Normal  SuccessfulRescale  patient-service  New size: 3; reason: cpu resource utilization above target
  Normal  SuccessfulRescale  patient-service  New size: 1; reason: All metrics below target
```

---

## Step 9 — Understand HPA limits

Try to force HPA to exceed maxReplicas by running an even heavier load:

```bash
hey -z 60s -c 200 http://localhost/patients/patients
```

No matter how high the CPU goes, HPA will never create more than 5 pods
(your `maxReplicas: 5`). This is a safety cap — in production you set it
based on your database's max connections and your node capacity.

---

## Step 10 — Reduce the scale-down delay (optional experiment)

The 5-minute cooldown is configurable. To see scale-down happen faster:

```bash
kubectl patch hpa patient-service -n dev --patch \
  '{"spec":{"behavior":{"scaleDown":{"stabilizationWindowSeconds":60}}}}'
```

Now run the load test again, stop it, and watch — it will scale down after ~1 minute
instead of 5. This is useful for dev environments where you want to save resources faster.

Restore the default:
```bash
kubectl patch hpa patient-service -n dev --patch \
  '{"spec":{"behavior":{"scaleDown":{"stabilizationWindowSeconds":300}}}}'
```

---

## HPA vs manual scaling

| | Manual `kubectl scale` | HPA |
|-|----------------------|-----|
| Who decides | You | Kubernetes controller |
| When it scales | When you run the command | When CPU crosses threshold |
| Speed | Immediate | ~60-90 second reaction time |
| Good for | One-off changes | Steady ongoing traffic |
| Risk | Forget to scale down | Flapping if threshold is too low |

In production you use HPA for normal traffic variation and manual scale for
known events (a marketing campaign, a batch job, a maintenance window).

---

## Key concepts learned

| Concept | What it means |
|---------|--------------|
| HPA | Controller that adjusts replica count based on metrics |
| metrics-server | Collects real-time CPU/memory from pods — HPA reads this |
| `targetCPUUtilizationPercentage` | Scale up when average pod CPU exceeds this % of its `requests.cpu` |
| `minReplicas` / `maxReplicas` | Hard floor and ceiling for scaling |
| Scale-down delay | 5-minute cooldown before removing pods (prevents flapping) |
| `stabilizationWindowSeconds` | How to configure the scale-down cooldown |

---

## Done when
- `kubectl get hpa -n dev` shows patient-service HPA with a CPU target
- You ran a load test and watched pods scale from 1 → 3+ automatically
- You stopped the load and watched pods scale back down after the cooldown
- You read the HPA events with `kubectl describe hpa`
