# AGENTS.md

FastAPI learning project (`app/main.py` → `app.main:app`) with sklearn `/predict`, Anthropic `/chat`, plus k8s practice manifests. No CI, no lint/typecheck config, no package manager beyond pip + `requirements.txt`.

## Commands

- Tests: `.venv/bin/python -m pytest -q` — single test: `.venv/bin/python -m pytest tests/test_health.py -q`
  - Note `.vscode/settings.json` enables unittest discovery, but the repo's only test suite is pytest; run pytest explicitly.
- Dev server: `.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8888` — port is **8888**, not the 8000 default (Dockerfile, k8s Service, probes all assume 8888).
- Lint/format (no config files, tools only listed in `requirements.txt`): `ruff check .`, `black .`
- Docker: `docker build -t py-app:local .` — heavy (>2GB: `torch`, `torchvision`, `opencv-python` installed but unused by the running routes), so builds/loads are slow.

## Architecture / gotchas

- Entrypoints: `app/main.py` wires `health`, `predict`, `chat` routers from `app/api/routes/`. Schemas in `app/schemas/common.py`. `app/cv/processor.py` and torch/pandas/sqlalchemy are currently dead code — don't assume they're wired in.
- Config: `app/core/config.py` uses `pydantic-settings` (`APP_NAME`, `DEBUG`, `DATABASE_URL`, `ANTHROPIC_API_KEY`, `.env` file). `get_settings()` is `@lru_cache`d — env is read once at import, so **config changes require a process/pod restart**, never hot-reload.
- Secrets: copy `.env.example` to `.env` (gitignored). Never commit real keys; `k8s/secret.yaml` ships with an empty `ANTHROPIC_API_KEY` placeholder.
- `/predict` returns **400 until trained by design**: `RegressionModel` (`app/ml/model.py`) is a module-global that starts unfitted and nothing trains it at startup. `/chat` (`app/llm/client.py`, model `claude-sonnet-5`) calls the real Anthropic API — no key = failure, don't hit it in automated tests.

## Kubernetes (see `docs.md` for full walkthrough)

- Basic manifests: `k8s/{configmap,secret,deployment,service}.yaml`. `k8s/advanced/` is opt-in practice material (postgres, hpa, ingress, networkpolicy, cronjob, namespace) — **do not `kubectl apply` it by default**.
- kind flow: `kind create cluster --name py-practice` → `docker build -t py-app:local .` → `kind load docker-image py-app:local --name py-practice` → `kubectl apply -f k8s/`. `imagePullPolicy: IfNotPresent` means pods will fail with `ImagePullBackOff` if you skip the `kind load` step. Docker Desktop Kubernetes skips `kind load` (shared daemon).
- `kubectl rollout restart deployment py-app` is required after **both** kinds of change: rebuilding the image under the same `:local` tag (tag string unchanged, so no auto-update), and editing ConfigMap/Secret (`envFrom` does not watch for changes). `kubectl port-forward svc/py-app 8888:8888` is needed to reach the `ClusterIP` service locally.
