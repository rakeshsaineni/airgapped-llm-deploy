# Runbook: install into an air-gapped cluster

**Outside (connected build machine)**

1. Render with the air-gap values and check policy:
   `helm template demo charts/llm-stack -f charts/llm-stack/values-airgap.yaml > rendered.yaml`
   `airgap lint rendered.yaml --profile airgap --registry registry.plant.internal:5000`
2. Build the bundle from the **public** image references (default values):
   `helm template demo charts/llm-stack > public.yaml && airgap bundle public.yaml --out bundle/`
3. Record the SHA-256 of `bundle/bundle-manifest.json` in the change ticket. Transfer `bundle/` on approved media.
4. Model weights travel separately (they are large). Copy them into the `llm-models` volume and checksum them the same way.

**Inside (disconnected network)**

1. Verify before touching anything: `airgap verify bundle/`. Stop if anything is reported.
2. Load, retag and push to the internal registry: `airgap push bundle/ --registry registry.plant.internal:5000`.
3. Put the digests from the push output into `values-airgap.yaml` (digests, not tags).
4. Install: `helm upgrade --install demo bundle/llm-stack.tgz -f values-airgap.yaml --namespace llm --create-namespace`.
5. Check: pods are Ready, `kubectl get networkpolicy -n llm` shows the default deny, and `/health` responds through the ingress.
