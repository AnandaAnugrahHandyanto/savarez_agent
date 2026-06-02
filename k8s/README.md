# Kubernetes terminal backend — deployment samples

Manifests for running Hermes' [`kubernetes` terminal backend](../tools/environments/kubernetes.py) safely on a real cluster. The backend runs each agent shell command in a fresh **session pod** instead of in the agent's own container, giving you isolation from the agent's home, secrets, and ServiceAccount token.

This directory ships two pieces a cluster operator needs:

| File | What it is | Why |
|---|---|---|
| [`rbac.yaml`](./rbac.yaml) | Scoped `Role` + `RoleBinding` + no-perms session `ServiceAccount` | Grant the agent SA *only* the verbs it needs (pods, pods/exec, pods/log, PVCs) in its own namespace. |
| [`validatingadmissionpolicy.yaml`](./validatingadmissionpolicy.yaml) | Cluster `ValidatingAdmissionPolicy` + binding | Constrain the *shape* of session pods so a granted `pods/create` cannot mean "create a privileged pod". |

**You almost certainly want both.** "`pods/create` in a namespace" without admission constraints is effectively namespace-admin (a pod can set `serviceAccountName`, mount any Secret, mount any PVC). The VAP is what makes the RBAC grant safe.

## Apply

```bash
# 1. Edit rbac.yaml: replace <AGENT_NAMESPACE> + <AGENT_SA> with your values.
kubectl apply -f rbac.yaml

# 2. Apply the cluster-wide admission policy (one-time, k8s >= 1.30).
kubectl apply -f validatingadmissionpolicy.yaml
```

Then run the agent with `TERMINAL_ENV=kubernetes` and the related `TERMINAL_KUBERNETES_*` env vars (see [`.env.example`](../.env.example)).

## Verifying

The scoped grant:

```bash
SA=system:serviceaccount:<AGENT_NAMESPACE>:<AGENT_SA>
kubectl auth can-i create pods       --as=$SA -n <AGENT_NAMESPACE>   # yes
kubectl auth can-i create pods/exec  --as=$SA -n <AGENT_NAMESPACE>   # yes
kubectl auth can-i create deployments --as=$SA -n <AGENT_NAMESPACE>  # no  (not granted)
kubectl auth can-i create secrets    --as=$SA -n <AGENT_NAMESPACE>   # no  (not granted)
```

The VAP enforcement (a deny path with a clear message is your signal it works):

```bash
# A compliant labeled session pod should be allowed:
kubectl --as=$SA apply -f compliant-pod.yaml

# A pod with hostPID: true should be denied with:
#   "hostPID is not allowed for session pods"
kubectl --as=$SA apply -f privileged-pod.yaml
```

## Notes / hardening

- **Label-based scoping.** The VAP binds via the `app.kubernetes.io/managed-by: hermes-agent` label the backend stamps on every session pod. A compromised agent could in principle omit the label to dodge the policy — the RBAC grant only includes `pods/create` (no privileged-pod-specific verbs), but if you operate in a multi-tenant cluster consider scoping the VAP binding by `namespaceSelector` (restrict to your hermes namespaces) and/or scoping further by the creating SA's username.
- **Namespace scoping.** The `Role`/`RoleBinding` are namespace-scoped — the agent can only create session pods in its own namespace.
- **Session SA holds nothing.** `hermes-session-noperms` carries no permissions and the manifest sets `automountServiceAccountToken: false`. The backend additionally sets it false at pod level, so a compromised session pod has no API access.
- **Pod security context.** The backend always sets `runAsNonRoot`, a non-zero `runAsUser`/`fsGroup`, `drop ALL` capabilities, and `allowPrivilegeEscalation: false`. The VAP enforces those, so a future regression in the backend can't quietly relax them.

## Operator-managed alternative

If you'd rather not manage these manifests by hand, the [**hermes-operator**](https://github.com/UndermountainCC/hermes-operator) (going public soon) reconciles the RBAC and the VAP automatically when you set `spec.execBackend: kubernetes` on a `HermesAgent` custom resource — including a stricter VAP scoped to operator-managed pods. The samples in this directory are a clean baseline if you're not using the operator (or as a reference if you're hand-rolling something similar).
