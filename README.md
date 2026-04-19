# Helm - корпоративный AI-ассистент

Helm - продукт для автоматизации офисной работы с помощью AI. Умный роутер автоматически выбирает лучшую модель под каждый тип задачи: код, аналитика, документы, голос, изображения.

Целевая аудитория - компании от 50 до 300 сотрудников, которые хотят внедрить AI без раздутых бюджетов и зависимости от одного провайдера.

---

## Что работает

### AI-роутинг

Система автоматически определяет тип задачи и выбирает оптимальную модель:

| Тип задачи | Модель | Провайдер |
|-----------|--------|-----------|
| Текст, общение | Llama 3.3 70B | routerai.ru / OpenRouter |
| Код, разработка | Qwen 2.5 Coder 32B | routerai.ru / OpenRouter |
| Глубокий анализ, стратегия | DeepSeek R1 | routerai.ru / OpenRouter |
| Анализ изображений | Llama 3.2 90B Vision | routerai.ru / OpenRouter |
| Генерация изображений | FLUX.2 Pro (или любая из 353) | routerai.ru / OpenRouter |
| Голос -> текст | Whisper Large v3 Turbo | Groq |
| Ответы по документам (RAG) | Llama 3.3 70B + ChromaDB | routerai.ru / OpenRouter |

Классификатор задач - `gemma-3-4b-it` (~200ms). Для очевидных случаев (блоки кода, SQL) - мгновенный pre-check без обращения к модели. Повторные запросы - LRU-кеш на 500 записей.

### Backend (FastAPI)

- Аутентификация - JWT access + refresh токены, bcrypt пароли, logout с отзывом токена
- Чаты - история, стриминг ответов через SSE, пагинация, кастомный system prompt на чат
- Поиск - полнотекстовый поиск по чатам и сообщениям
- Экспорт - скачать чат в Markdown или PDF
- Воркспейсы - разграничение данных между командами, управление участниками
- RAG-пайплайн - загрузка PDF/DOCX/TXT, автоиндексация в ChromaDB, семантический поиск (локальные ONNX-эмбеддинги)
- Долгосрочная память - автоматическое извлечение фактов о пользователе, инжект в system prompt
- Файлы - загрузка документов, аудио, изображений (до 50 МБ, лимит 50 файлов / 500 МБ на пользователя)
- Профиль - смена имени, пароля
- Роли - admin / user, панель администратора со статистикой

### Производительность

- Постоянный пул HTTP-соединений с keep-alive (нет TLS handshake на каждый запрос)
- Умная обрезка истории чата по токенам (лимит 6000, ~4 символа/токен)
- Пагинация на всех list-эндпоинтах (чаты: до 100 на страницу, сообщения: до 200)
- LRU-кеш классификатора + мгновенный pre-check для кода

### Надёжность

- Retry с exponential backoff - 5 попыток (1s, 2s, 4s, 8s) при сетевых ошибках и 5xx
- Rate limiting - 20 запросов/минуту на пользователя, HTTP 429 с Retry-After
- Таймаут генерации - 90 секунд, после чего стрим закрывается с ошибкой
- Детальный healthcheck - `GET /api/health/detailed` проверяет доступность routerai.ru

### Безопасность

- Валидация MIME-типа по magic bytes файла (не по заголовку Content-Type)
- Лимит файлов: 50 файлов и 500 МБ суммарно на пользователя
- Refresh token blacklist - отзыв токенов при logout, ротация при каждом /refresh

### DevOps

- **Structured JSON logging** — каждая строка лога — валидный JSON, Grafana Loki подхватывает без парсинга
- **Prometheus метрики** — `GET /api/metrics`; LLM-latency (до первого токена + полный стрим), токены/запрос, ошибки, rate-limit hits, cache hits классификатора
- **Alembic миграции** — версионированные миграции вместо ручных ALTER TABLE; `alembic upgrade head` при старте
- **docker-compose.prod.yml** — Nginx reverse-proxy (порт 80), gunicorn с 4 uvicorn-воркерами, Prometheus + Grafana в комплекте
- **Nginx** — rate-limit по IP, отдельные таймауты для SSE/файлов/генерации, метрики не торчат наружу

### Развёртывание

- **Cloud-режим** - routerai.ru или любой OpenRouter-совместимый провайдер + Groq
- **Local-режим** - полностью локально через Ollama (для 152-ФЗ и air-gapped окружений)
- **Dev** - `docker compose up db backend -d` — поднимает PostgreSQL + бэкенд одной командой
- **Prod** - `docker compose -f docker-compose.prod.yml up -d --build` — gunicorn + мониторинг

---

## Стек

**Backend:** Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL, ChromaDB  
**AI:** routerai.ru (OpenRouter-совместимый), Groq, Ollama  
**Инфра:** Docker, Docker Compose, Alembic, Prometheus, Grafana  
**Embedding:** ONNX MiniLM L6 v2 (локально, без API)

---

## Быстрый старт

```bash
git clone https://github.com/pro1chuh/helmgate_ai
cd helmgate_ai
cp .env.example .env
# Заполни OPENROUTER_API_KEY и GROQ_API_KEY в .env
docker compose up db backend -d
```

API-документация: `http://localhost:8000/api/docs`

---

## Переменные окружения

```env
DEPLOYMENT_MODE=cloud          # cloud | local

# LLM - routerai.ru или openrouter.ai
OPENROUTER_API_KEY=sk-...
OPENROUTER_BASE_URL=https://routerai.ru/api/v1

# ASR - только Groq (Whisper)
GROQ_API_KEY=gsk_...
```

В `local`-режиме нужен только Ollama - никаких внешних API.

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
POST   /api/chats                        -- title, system_prompt
PATCH  /api/chats/{id}                   -- обновить заголовок / system prompt
DELETE /api/chats/{id}
GET    /api/chats/search?q=...           -- поиск по чатам и сообщениям
GET    /api/chats/{id}/messages?page=1&limit=50
POST   /api/chats/{id}/messages          -- SSE stream
GET    /api/chats/{id}/export?format=md  -- экспорт в Markdown
GET    /api/chats/{id}/export?format=pdf -- экспорт в PDF

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

POST   /api/images/generate              -- генерация изображений (FLUX / DALL-E / SD)

GET    /api/admin/users                  -- только admin
PATCH  /api/admin/users/{id}
GET    /api/admin/stats

GET    /api/health
GET    /api/health/detailed              -- статус + latency провайдера
GET    /api/metrics                      -- Prometheus scrape endpoint
```

---

## SSE-стрим

Каждый ответ модели приходит тремя типами событий:

```
data: {"type": "meta", "task_type": "code", "model": "qwen/qwen2.5-coder-32b-instruct"}
data: {"type": "token", "content": "def "}
data: {"type": "token", "content": "reverse..."}
data: {"type": "done", "message_id": 42}
```

При ошибке LLM стрим не падает - клиент получает `{"type": "error", "detail": "..."}` и соединение закрывается корректно.

---

## Мониторинг (prod)

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (admin / значение `GRAFANA_PASSWORD` из `.env`)
- Метрики бэкенда: `http://localhost:8000/api/metrics`

Ключевые метрики:
- `helm_llm_first_token_seconds` — latency до первого токена по провайдеру/модели/типу задачи
- `helm_llm_stream_duration_seconds` — полная длительность стрима
- `helm_llm_tokens_total` — токенов сгенерировано (по модели)
- `helm_llm_requests_total` — запросов к LLM (с разбивкой по статусу ok/error/timeout)
- `helm_rate_limit_hits_total` — сколько раз сработал rate-limiter
- `helm_classifier_cache_hits_total` — попадания в LRU-кеш классификатора

---

## Alembic миграции

```bash
# Применить все миграции (автоматически при старте приложения)
docker compose exec backend alembic upgrade head

# Создать новую миграцию после изменения модели
docker compose exec backend alembic revision --autogenerate -m "add_column_x"

# Откатить последнюю миграцию
docker compose exec backend alembic downgrade -1
```

---

## Roadmap

- [ ] Next.js фронтенд (Dmitry, в разработке)
- [ ] Голосовой вывод TTS
- [ ] SSO / LDAP для корпоративных клиентов

---

## Команда

- Backend, AI-инфраструктура - Anatoly Prochukhan
- Frontend - Dmitry Godovec

Telegram: [@helmgate](https://t.me/helmgate)
