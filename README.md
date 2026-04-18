# Helm - корпоративный AI-ассистент

Helm - это продукт для автоматизации работы в офисе с помощью искусственного интеллекта. Умный роутер автоматически выбирает лучшую модель под каждый тип задачи: код, аналитика, документы, голос, изображения.

Целевая аудитория - компании от 50 до 300 сотрудников, которые хотят внедрить AI без раздутых бюджетов и зависимости от одного провайдера.

---

## Что уже работает

### AI-роутинг
Система автоматически определяет тип задачи и выбирает оптимальную модель:

| Тип задачи | Модель | Провайдер |
|-----------|--------|-----------|
| Текст, общение | Llama 3.3 70B | NVIDIA NIM |
| Код, разработка | Qwen 2.5 Coder 32B | NVIDIA NIM |
| Глубокий анализ, стратегия | GLM-5.1 (thinking) | NVIDIA NIM |
| Анализ изображений | Llama 3.2 90B Vision | NVIDIA NIM |
| Голос -> текст | Whisper Large v3 Turbo | Groq |
| Ответы по документам (RAG) | Llama 3.3 70B + ChromaDB | NVIDIA NIM |

Классификатор задач - `gemma-3-4b-it` (быстрая, ~200ms, бесплатная).

### Backend (FastAPI)
- Аутентификация - JWT access + refresh токены, bcrypt пароли
- Чаты - история, стриминг ответов через SSE (Server-Sent Events)
- RAG-пайплайн - загрузка PDF/DOCX/TXT, автоиндексация в ChromaDB, семантический поиск
- Долгосрочная память - автоматическое извлечение фактов о пользователе из диалогов
- Файлы - загрузка документов, аудио, изображений (до 50 МБ)
- Профиль - смена имени, пароля
- Роли - admin / user, панель администратора со статистикой

### Развёртывание
- **Cloud-режим** - NVIDIA NIM + Groq, запускается одной командой
- **Local-режим** - полностью локально через Ollama (для 152-ФЗ и air-gapped окружений)
- Docker Compose - поднимает PostgreSQL, бэкенд, Ollama одной командой

---

## Стек

**Backend:** Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL, ChromaDB  
**AI:** NVIDIA NIM, Groq, Ollama  
**Инфра:** Docker, Docker Compose  
**Embedding:** nvidia/nv-embedqa-e5-v5

---

## Быстрый старт

```bash
git clone https://github.com/pro1chuh/helmgate_ai
cd helmgate_ai
cp .env.example .env
# Заполни NVIDIA_API_KEY и GROQ_API_KEY в .env
docker compose up db backend -d
```

API-документация: `http://localhost:8000/api/docs`

---

## API

```
POST   /api/auth/register       - регистрация
POST   /api/auth/login          - вход
POST   /api/auth/refresh        - обновление токена

GET    /api/profile             - профиль
PATCH  /api/profile             - обновить имя
POST   /api/profile/change-password

GET    /api/chats               - список чатов
POST   /api/chats               - новый чат
DELETE /api/chats/{id}
GET    /api/chats/{id}/messages
POST   /api/chats/{id}/messages - отправить сообщение (SSE stream)

GET    /api/files               - список файлов
POST   /api/files               - загрузить файл
DELETE /api/files/{id}

GET    /api/memory              - факты о пользователе
PUT    /api/memory/{key}        - сохранить факт
DELETE /api/memory/{key}

GET    /api/admin/users         - все пользователи (admin)
PATCH  /api/admin/users/{id}    - блокировка / смена роли (admin)
GET    /api/admin/stats         - статистика системы (admin)
```

---

## Архитектура SSE-стрима

Каждый ответ модели приходит тремя типами событий:

```
data: {"type": "meta", "task_type": "code", "model": "qwen/qwen2.5-coder-32b-instruct"}
data: {"type": "token", "content": "def "}
data: {"type": "token", "content": "reverse..."}
data: {"type": "done", "message_id": 42}
```

Фронтенд получает токены в реальном времени и рендерит их по мере поступления.

---

## Roadmap

- [ ] Next.js фронтенд (в разработке)
- [ ] Генерация изображений (FLUX через NVIDIA NIM)
- [ ] SSO / LDAP для корпоративных клиентов
- [ ] Аудит-лог действий пользователей
- [ ] Workspace - разграничение данных между отделами
- [ ] Мобильное приложение

---

## Команда

Проект разрабатывается командой из двух человек:
- Backend, AI-инфраструктура - Anatoly Prochukhan
- Frontend - в разработке

Telegram-канал с обновлениями: [@helmgate](https://t.me/helmgate)
