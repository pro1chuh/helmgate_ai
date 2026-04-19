# Helm — корпоративный AI-ассистент

Helm — продукт для автоматизации офисной работы с помощью AI. Умный роутер автоматически выбирает лучшую модель под каждый тип задачи: код, аналитика, документы, голос, изображения.

Целевая аудитория — компании от 50 до 300 сотрудников, которые хотят внедрить AI без раздутых бюджетов и зависимости от одного провайдера.

---

## Что работает

### AI-роутинг

Система автоматически определяет тип задачи и выбирает оптимальную модель. Все запросы идут через OpenRouter (routerai.ru), ASR — через Groq.

| Тип задачи | Модель | Провайдер |
|---|---|---|
| Текст, общение | Llama 3.3 70B | OpenRouter |
| Код, разработка | KAT-Coder-Pro V2 | OpenRouter |
| Глубокий анализ, стратегия | Gemini 2.5 Pro | OpenRouter |
| Анализ изображений | Grok 4.20 Vision | OpenRouter |
| Генерация изображений | Gemini 2.5 Flash Image | OpenRouter |
| Голос → текст (ASR) | Whisper Large v3 Turbo | Groq |
| Ответы по документам (RAG) | Llama 3.3 70B + ChromaDB | OpenRouter |
| AI-классификатор запросов | Gemma 3 4B | OpenRouter |

Классификатор определяет тип задачи (~200–400 мс). Для очевидных случаев (блоки кода, SQL-запросы) — мгновенный pre-check без LLM. Повторные запросы — LRU-кеш на 500 записей.

---

### Backend (FastAPI)

**Аутентификация**
- JWT access + refresh токены, bcrypt пароли
- Logout с отзывом токена (refresh token blacklist)
- Ротация токенов при каждом `/refresh`

**Чаты**
- История, стриминг ответов через SSE
- Пагинация (до 100 чатов / 200 сообщений на страницу)
- Кастомный system prompt на каждый чат
- Полнотекстовый поиск по чатам и сообщениям
- Экспорт в Markdown и PDF

**Файлы и RAG**
- Загрузка PDF, DOCX, TXT, аудио, изображений (до 50 МБ)
- Лимит: 50 файлов / 500 МБ на пользователя
- Автоиндексация документов в ChromaDB
- Семантический поиск при ответе на вопросы по документу

**Воркспейсы**
- Разграничение данных между командами
- Управление участниками

**Долгосрочная память**
- Автоматическое извлечение фактов о пользователе через Gemma 3 4B
- Инжект персональных фактов в system prompt каждого чата

**Биллинг (B2B)**
- Организации с балансом (рубли, 6 знаков)
- Точный подсчёт токенов через `stream_options.include_usage` от провайдера
- Логирование каждого запроса в `usage_logs` с реальной стоимостью
- История пополнений баланса
- Автоматическое приостановление при нулевом балансе

**Роли и управление**
- Роли: `user` / `admin` / `superadmin`
- Панель администратора (статистика, управление пользователями)
- Суперадмин-панель (организации, пополнение баланса, аналитика)

---

### Новые возможности (v2)

**Redis-кеш**
- Распределённый кеш на Redis 7 (256 MB, LRU eviction)
- Суточные счётчики токенов на пользователя (TTL до конца UTC-суток)
- Graceful degradation — при недоступности Redis приложение продолжает работу

**Суточный лимит токенов**
- Настраиваемый лимит на пользователя (`daily_token_limit`)
- Глобальный дефолт через `DEFAULT_DAILY_TOKEN_LIMIT` в `.env`
- HTTP 429 при превышении, сброс в полночь UTC

**Circuit breaker**
- Отслеживает сбои LLM-провайдера в Redis (общее состояние между воркерами)
- После N ошибок подряд блокирует запросы на период cooldown
- Автоматически сбрасывается при первом успешном запросе

**Алерты о низком балансе**
- Telegram-уведомление при пересечении порога (настраивается в `.env`)
- Флаг `low_balance_notified` — алерт один раз, сбрасывается при пополнении
- Отдельный алерт при полном обнулении баланса

**Webhooks**
- Подписки на события: `message.created`, `balance.low`, `balance.exhausted`, `chat.created`
- HMAC-SHA256 подпись каждого запроса (`X-Helm-Signature`)
- Управление через API: создать, включить/выключить, удалить

**Audit Log**
- Журнал административных действий (пополнение баланса, изменение ролей, webhooks)
- Просмотр через `GET /api/audit` (admin/superadmin)

**Batch API**
- Обработка до 10 сообщений за один запрос
- Реальный подсчёт токенов, суммарный биллинг
- Опциональное сохранение в чат

---

### Производительность

- Постоянный пул HTTP-соединений с keep-alive (нет TLS handshake на каждый запрос)
- Отдельный httpx-клиент для стриминга (не блокирует пул обычных запросов)
- Умная обрезка истории чата по токенам (лимит 6000)
- LRU-кеш классификатора + мгновенный pre-check для структурированного кода

### Надёжность

- Retry с exponential backoff — 5 попыток (1s, 2s, 4s, 8s) при сетевых ошибках и 5xx
- Circuit breaker — автоматический failover при деградации провайдера
- Rate limiting — 20 запросов/минуту на пользователя, HTTP 429 с `Retry-After`
- Таймаут генерации — 90 секунд, после чего стрим закрывается корректно

### Безопасность

- Валидация MIME-типа файлов по magic bytes (не по Content-Type)
- Webhook HMAC-SHA256 подпись для верификации получателем
- Refresh token blacklist в PostgreSQL
- Audit log всех административных действий

### DevOps

- **Structured JSON logging** — каждая строка лога — валидный JSON
- **Prometheus метрики** — `GET /api/metrics`; LLM-latency, токены, ошибки, rate-limit, cache hits
- **docker-compose.prod.yml** — Nginx reverse-proxy, gunicorn с 4 uvicorn-воркерами, Prometheus + Grafana
- **Nginx** — rate-limit по IP, отдельные таймауты для SSE/файлов/генерации

---

## Стек

**Backend:** Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL 16  
**Cache:** Redis 7  
**AI:** OpenRouter (routerai.ru) — все LLM; Groq — ASR  
**RAG:** ChromaDB, ONNX embeddings  
**Инфра:** Docker, Docker Compose, Prometheus, Grafana, Nginx  

---

## Быстрый старт

```bash
git clone https://github.com/pro1chuh/helmgate_ai
cd helmgate_ai
cp .env.example .env
# Заполни OPENROUTER_API_KEY и GROQ_API_KEY в .env
docker compose up -d
```

API-документация: `http://localhost:8000/api/docs`

---

## Переменные окружения

```env
# LLM — routerai.ru или openrouter.ai
OPENROUTER_API_KEY=sk-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# ASR — Groq (Whisper)
GROQ_API_KEY=gsk_...

# Redis (автоподключение при docker compose up)
REDIS_URL=redis://redis:6379/0

# Биллинг-алерты (опционально)
LOW_BALANCE_THRESHOLD_RUB=100
TELEGRAM_ALERT_TOKEN=
TELEGRAM_ALERT_CHAT_ID=

# Суточный лимит токенов (0 = без ограничений)
DEFAULT_DAILY_TOKEN_LIMIT=0

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
CIRCUIT_BREAKER_COOLDOWN_SECONDS=60
```

---

## API

```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/refresh
POST   /api/auth/logout

GET    /api/profile
PATCH  /api/profile
POST   /api/profile/change-password

GET    /api/chats?page=1&limit=20
POST   /api/chats
PATCH  /api/chats/{id}
DELETE /api/chats/{id}
GET    /api/chats/search?q=...
GET    /api/chats/{id}/messages?page=1&limit=50
POST   /api/chats/{id}/messages          -- SSE stream
GET    /api/chats/{id}/export?format=md
GET    /api/chats/{id}/export?format=pdf

GET    /api/files
POST   /api/files
DELETE /api/files/{id}

GET    /api/memory
PUT    /api/memory/{key}
DELETE /api/memory/{key}

GET    /api/workspaces
POST   /api/workspaces
PATCH  /api/workspaces/{id}
DELETE /api/workspaces/{id}
GET    /api/workspaces/{id}/members
POST   /api/workspaces/{id}/members
DELETE /api/workspaces/{id}/members/{user_id}

POST   /api/images/generate

POST   /api/batch                        -- до 10 сообщений без стриминга

GET    /api/webhooks
POST   /api/webhooks
PATCH  /api/webhooks/{id}/toggle
DELETE /api/webhooks/{id}

GET    /api/audit?page=1&limit=50        -- журнал действий (admin+)

GET    /api/admin/users
PATCH  /api/admin/users/{id}
GET    /api/admin/stats

GET    /api/superadmin/stats
GET    /api/superadmin/organizations
POST   /api/superadmin/organizations
GET    /api/superadmin/organizations/{id}
PATCH  /api/superadmin/organizations/{id}
DELETE /api/superadmin/organizations/{id}
POST   /api/superadmin/organizations/{id}/topup
GET    /api/superadmin/organizations/{id}/topups
GET    /api/superadmin/organizations/{id}/usage
GET    /api/superadmin/organizations/{id}/users
POST   /api/superadmin/organizations/{id}/invite

GET    /api/health
GET    /api/health/detailed
GET    /api/metrics
```

---

## SSE-стрим

```
data: {"type": "meta", "task_type": "code", "model": "kwaipilot/kat-coder-pro-v2"}
data: {"type": "token", "content": "def "}
data: {"type": "token", "content": "reverse..."}
data: {"type": "done", "message_id": 42}
```

При ошибке клиент получает `{"type": "error", "detail": "..."}` и соединение закрывается корректно.

---

## Мониторинг (prod)

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (admin / `GRAFANA_PASSWORD` из `.env`)
- Метрики: `http://localhost:8000/api/metrics`

Ключевые метрики:

| Метрика | Описание |
|---|---|
| `helm_llm_first_token_seconds` | Latency до первого токена |
| `helm_llm_stream_duration_seconds` | Полная длительность стрима |
| `helm_llm_tokens_total` | Токенов сгенерировано (по модели) |
| `helm_llm_requests_total` | Запросов к LLM (ok/error) |
| `helm_rate_limit_hits_total` | Срабатываний rate-limiter |
| `helm_classifier_cache_hits_total` | Попаданий в кеш классификатора |

---

## Roadmap

- [ ] Next.js фронтенд (в разработке)
- [ ] Голосовой вывод TTS
- [ ] SSO / LDAP для корпоративных клиентов
- [ ] Alembic миграции вместо fallback create_all

---

## Команда

- Backend, AI-инфраструктура — Anatoly Prochukhan
- Frontend — Dmitry Godovec

Telegram: [@helmgate](https://t.me/helmgate)
