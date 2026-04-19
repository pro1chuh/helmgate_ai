"""
Prometheus-метрики для Helm.

Экспортируются на GET /api/metrics (только для внутренних сервисов).

Доступные метрики:
  helm_llm_requests_total{provider, model, task_type, status}
  helm_llm_first_token_seconds{provider, model, task_type}   — время до первого токена
  helm_llm_stream_duration_seconds{provider, model}          — полная длительность стрима
  helm_llm_tokens_total{model}                               — токенов выдано (приближение)
  helm_rate_limit_hits_total                                 — сколько раз сработал rate-limiter
  helm_classifier_cache_hits_total                           — попадания в LRU-кеш классификатора
  helm_classifier_quick_hits_total                           — bypasses через quick-classify
"""
from prometheus_client import Counter, Histogram

# --- LLM-запросы ---

llm_requests_total = Counter(
    "helm_llm_requests_total",
    "Total LLM streaming requests",
    ["provider", "model", "task_type", "status"],  # status: ok | error | timeout
)

llm_first_token_seconds = Histogram(
    "helm_llm_first_token_seconds",
    "Time to first token from the provider",
    ["provider", "model", "task_type"],
    buckets=[0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

llm_stream_duration_seconds = Histogram(
    "helm_llm_stream_duration_seconds",
    "Total streaming duration including all tokens",
    ["provider", "model"],
    buckets=[1, 2, 5, 10, 20, 45, 90],
)

llm_tokens_total = Counter(
    "helm_llm_tokens_total",
    "Approximate number of tokens streamed (1 token ≈ 4 chars)",
    ["model"],
)

# --- Rate limiter ---

rate_limit_hits_total = Counter(
    "helm_rate_limit_hits_total",
    "Number of requests rejected by the rate limiter",
)

# --- Классификатор ---

classifier_cache_hits_total = Counter(
    "helm_classifier_cache_hits_total",
    "LRU cache hits in the task classifier",
)

classifier_quick_hits_total = Counter(
    "helm_classifier_quick_hits_total",
    "Quick structural pre-check hits (no model call needed)",
)
