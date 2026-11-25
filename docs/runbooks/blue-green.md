# Runbook: blue-green release and rollback

The chart renders one Deployment per entry in `api.colors`, and the Service routes to `api.activeColor` only.

1. **Deploy green next to blue.** Set `api.colors: [blue, green]`, point green at the new image digest, and `helm upgrade`. Blue still serves 100% of traffic.
2. **Test green directly.** `kubectl port-forward deploy/demo-llm-stack-api-green 8000` and run the smoke tests and the eval suite (`policyrag eval`) against it.
3. **Cut over.** Set `api.activeColor: green` and `helm upgrade`. This is a Service selector change: instant, with no pod restarts.
4. **Roll back** (if error rate or latency alarms fire): set `api.activeColor: blue` and upgrade again. Blue is still warm, so rollback takes seconds. `helm rollback demo <revision>` works too.
5. **Clean up** after a bake period: set `api.colors: [green]`.

Why not a rolling update? For an AI service, "new version" usually means a new model or prompt. You want to evaluate it on real infrastructure **before** any user sees it, and roll back without waiting for pods to start.
