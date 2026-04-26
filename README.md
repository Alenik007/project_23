# Проект 25. Frontend для ИИ-приложения на React /
Next.js

## 1. Название и краткое описание

**GenAI API** — FastAPI-сервис для генерации текста дообученной моделью (LoRA). API дополнено базовыми production-механизмами: **ограничение частоты запросов (rate limiting)**, **валидация входных данных (Pydantic)**, **простой фильтр типичных паттернов prompt injection**, **CORS** и эндпоинтом **`/generate/stream`** для чата. В **том же репозитории** лежит веб-интерфейс **`ai-chat-frontend/`** (Next.js 14, TypeScript, Tailwind): чат с потоковой подстановкой ответа, историей сессии, **AbortController** (Stop) и деплоем на **Vercel** (подробно — **раздел 16**). Бэкенд собирается в Docker, тестируется в GitHub Actions и разворачивается на **AWS** (публичный URL вместо Railway из формулировки задания).

## 2. Реализованные механизмы безопасности

| Механизм | Реализация |
|----------|------------|
| **Rate limiting** | [slowapi](https://github.com/laurentS/slowapi): не более **10 запросов в минуту на IP** для `POST /generate` и отдельно для `POST /generate/stream`; при превышении — **HTTP 429** с полем `detail`. |
| **CORS** | `CORSMiddleware`: список origin из переменной **`CORS_ORIGINS`** (через запятую). По умолчанию: `http://localhost:3000`. После деплоя фронта на Vercel добавьте URL вида `https://….vercel.app`. |
| **Streaming** | `POST /generate/stream` — `text/plain; charset=utf-8`: полный ответ модели затем отдаётся **по словам с паузой** (UX streaming). Нативный поток токенов из `transformers` в этом endpoint **не** используется. |
| **Pydantic validation** | Модель `GenerateRequest` в `app/models.py`: ограничения по длине и содержимому `prompt`, диапазоны `max_tokens` и `temperature`; ошибки — **HTTP 422**. |
| **Prompt injection filter** | Функция `assert_prompt_not_injection` в `app/security.py`: нечувствительная к регистру проверка по списку подстрок; при совпадении — **HTTP 400** с сообщением *«Prompt rejected due to suspicious instruction pattern»*. |

**Важно:** фильтр prompt injection **базовый** (по ключевым фразам). Он снижает риск тривиальных атак на инструкции, но **не заменяет** полноценную защиту на уровне модели, политик контента, мониторинга и выделенных security-слоёв.

## 3. Ограничения API (`POST /generate`)

| Параметр | Правило |
|-----------|---------|
| **prompt** | Обязателен, после `strip` не пустой, максимум **2000** символов. |
| **max_tokens** | Целое **1–2048**, по умолчанию **256**. |
| **temperature** | **0.0–2.0**, по умолчанию **0.7**. |
| **Rate limit** | **10** запросов в минуту на **один IP** для каждого из эндпоинтов **`/generate`** и **`/generate/stream`** (отдельные счётчики). |

Успешный ответ (**HTTP 200**), минимальный JSON:

```json
{
  "result": "…сгенерированный текст…",
  "max_tokens": 256,
  "temperature": 0.7
}
```

В режиме заглушки (`USE_STUB` или отсутствие весов) в `result` будет префикс вида `[stub:…]`; при реальных весах — вывод модели.

## 4. Потоковый endpoint `POST /generate/stream`

Тело запроса — как у `/generate` (JSON, модель `GenerateRequest`). Успешный ответ — **HTTP 200**, тип **`text/plain; charset=utf-8`**, тело — поток фрагментов текста (на бэкенде сначала считается полный ответ модели, затем он отдаётся **по словам с паузой** — удобно для UI; нативный поток токенов из `transformers` в этом endpoint не используется).

Пример (bash / Git Bash; в PowerShell удобнее `curl.exe`):

```bash
curl -N -X POST "http://SERVER_IP:8000/generate/stream" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"Hello\",\"max_tokens\":256,\"temperature\":0.7}"
```

Флаг **`-N`** отключает буферизацию, чтобы куски приходили по мере отправки.

## 5. Пример успешного запроса (curl)

```bash
curl -X POST "http://SERVER_IP:8000/generate" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"Hello\",\"max_tokens\":256,\"temperature\":0.7}"
```

Ожидается **HTTP 200** и JSON с полями `result`, `max_tokens`, `temperature`.

## 6. Примеры ошибок

### HTTP 400 — отклонённый промпт (prompt injection)

```bash
curl -X POST "http://SERVER_IP:8000/generate" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"ignore previous instructions\",\"max_tokens\":256,\"temperature\":0.7}"
```

Пример ответа:

```json
{
  "detail": "Prompt rejected due to suspicious instruction pattern"
}
```

### HTTP 422 — ошибка валидации (пустой промпт)

```bash
curl -X POST "http://SERVER_IP:8000/generate" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"\",\"max_tokens\":256,\"temperature\":0.7}"
```

Тело ответа — стандартная структура FastAPI/Pydantic (`detail` как список объектов с `loc`, `msg`, `type`).

### HTTP 429 — превышен rate limit

Отправьте **более 10** успешных запросов к `/generate` с одного IP за минуту. Пример ответа:

```json
{
  "detail": "Rate limit exceeded: no more than 10 requests per minute per IP address are allowed."
}
```

## 7. Паттерны prompt injection (фильтруются)

Проверка выполняется по **нижнему регистру** текста промпта; при вхождении **любой** из подстрок запрос отклоняется (**400**):

1. `ignore previous instructions`
2. `ignore all previous instructions`
3. `system:`
4. `assistant:`
5. `developer:`
6. `you are now`
7. `act as`
8. `forget previous instructions`
9. `disregard previous instructions`

## 8. Запуск локально (Python 3.10+)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
set MODEL_PATH=model_weights
set MODEL_NAME=local-finetuned-model
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Документация: `http://localhost:8000/docs`

Без весов в `MODEL_PATH` сервис поднимается в режиме **заглушки** (`[stub:…]` в ответе).

## 9. Запуск через Docker

Сборка (имя образа можно заменить на `project-24` по заданию):

```bash
docker build -t project-24 .
```

Запуск:

```bash
docker run -d -p 8000:8000 --name project-24 project-24
```

Проверка:

```bash
curl -f http://localhost:8000/health
curl -f http://localhost:8000/docs
```

С переменными для весов (как в CI):

```bash
docker run -d -p 8000:8000 --name genai-api ^
  -e MODEL_PATH=/app/model_weights ^
  -e MODEL_NAME=local-finetuned-model ^
  -e HF_WEIGHTS_REPO=your-org/your-weights-repo ^
  -e HF_TOKEN=your_hf_token ^
  genai-api
```

## 10. Запуск тестов

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Файлы: `tests/test_validation.py`, `tests/test_rate_limit.py`, `tests/test_security.py`, `tests/test_stream.py`.

## 11. Структура приложения (целевая схема задания)

```
project_23/
├── ai-chat-frontend/     # Next.js 14 чат (см. README внутри каталога)
├── app/
│   ├── main.py
│   ├── models.py
│   ├── rate_limiter.py
│   ├── security.py
│   ├── config.py
│   ├── inference.py
│   └── model.py
├── tests/
│   ├── conftest.py
│   ├── test_validation.py
│   ├── test_rate_limit.py
│   ├── test_security.py
│   └── test_stream.py
├── Dockerfile
├── requirements.txt
└── README.md
```

## 12. Переменные окружения (инференс)

| Переменная | Назначение | Пример |
|------------|------------|--------|
| `MODEL_PATH` | Каталог с адаптером (LoRA) | `/app/model_weights` |
| `MODEL_NAME` | Имя модели (отображение) | `local-finetuned-model` |
| `HOST` / `PORT` | Uvicorn | `0.0.0.0` / `8000` |
| `BASE_MODEL_NAME` | Базовая модель HF | `Qwen/Qwen2.5-1.5B-Instruct` |
| `HF_WEIGHTS_REPO` | Репозиторий HF со снапшотом весов | `org/repo` |
| `HF_TOKEN` | Токен HF для приватных репозиториев | *(secret)* |
| `USE_STUB` | `1` / `true` — заглушка без torch | `0` |
| `CORS_ORIGINS` | Разрешённые origin для браузера (через запятую) | `http://localhost:3000,https://app.vercel.app` |

Полный список defaults: `app/config.py`.

Потоковый эндпоинт: **`POST /generate/stream`** (тело как у `/generate`, ответ `text/plain`). После деплоя фронта добавьте URL Vercel/Netlify в **`CORS_ORIGINS`** и перезапустите контейнер на AWS.

## 13. CI/CD и AWS

Файл `.github/workflows/deploy.yml`: **test** (pytest) → **build** (`docker build -t genai-api .`) → **deploy** (SSH: `git pull`, пересборка, `docker run`).

На **AWS Ubuntu** (после клонирования в каталог, например `/home/ubuntu/project_23` или `project_24`):

```bash
cd /home/ubuntu/project_23
git pull
docker stop genai-api 2>/dev/null || true
docker rm genai-api 2>/dev/null || true
docker build -t genai-api .
docker run -d --name genai-api --restart unless-stopped -p 8000:8000 \
  -e MODEL_PATH=/app/model_weights \
  -e MODEL_NAME=local-finetuned-model \
  -e CORS_ORIGINS="http://localhost:3000,https://ВАШ-ПРОЕКТ.vercel.app" \
  genai-api
curl -f http://localhost:8000/health
```

Подставьте реальный URL фронта с Vercel в **`CORS_ORIGINS`** (через запятую без пробелов или с пробелами — в `app/config.py` origin обрезаются). Для только локальной разработки достаточно значения по умолчанию `http://localhost:3000`.

```bash
# пример без Vercel (только локальный фронт)
docker run -d --name genai-api --restart unless-stopped -p 8000:8000 \
  -e MODEL_PATH=/app/model_weights \
  -e MODEL_NAME=local-finetuned-model \
  genai-api
curl -f http://localhost:8000/health
```

С внешней машины: `http://AWS_PUBLIC_IP:8000/docs`. В **Security Group** EC2 должны быть разрешены **22** (SSH) и **8000** (HTTP API).

Секреты GitHub: `AWS_HOST`, `AWS_USER`, `AWS_SSH_KEY`, `AWS_PROJECT_PATH`, `MODEL_PATH`, `MODEL_NAME`; опционально `HF_WEIGHTS_REPO`, `HF_TOKEN`.

## 14. Известные ограничения

- Веса LoRA в публичном репозитории не хранятся (`model_weights/` пустой, только `.gitkeep`); для продакшена задайте `HF_WEIGHTS_REPO` / том с весами.
- Инференс с `transformers` + `peft` + `torch` требует ресурсов; первый ответ может быть долгим.
- Rate limit и фильтр injection — **базовый** уровень защиты, не заменяют WAF, аутентификацию и политики на уровне организации.

## 15. Критерии готовности (чеклист сдачи)

**Backend**

1. Код в GitHub; корневой README и `requirements.txt` актуальны; Dockerfile собирается.
2. `pytest tests/` проходит (включая `test_stream.py`).
3. API: **200** — корректный запрос; **400** — injection; **422** — валидация; **429** — превышение лимита; поток **`/generate/stream`** отдаёт `text/plain`.
4. Проверка на AWS: `curl http://localhost:8000/docs` на сервере и доступ с браузера по публичному IP.
5. После появления URL фронта на Vercel — в **`CORS_ORIGINS`** на контейнере API указан этот origin, контейнер перезапущен.

**Frontend (монорепозиторий)**

6. В репозитории есть каталог **`ai-chat-frontend/`** с собственным [README](ai-chat-frontend/README.md); **`npm run lint`** и **`npm run build`** без ошибок; **`.env.local`** не коммитится (есть **`.env.example`**).
7. На Vercel (или Netlify) задан **`NEXT_PUBLIC_API_URL`** = `http://AWS_PUBLIC_IP:8000` (без завершающего `/`); в проекте Vercel при необходимости указан **Root Directory** `ai-chat-frontend`.
8. В корневом README или в `ai-chat-frontend/README.md` — ссылки на **задеплоенный фронт**, **backend URL**, при желании **скриншот/GIF** и **ссылку на демо-видео** (30–60 с: чат, streaming, вторая реплика, Stop/Clear, пример ошибки).

## 16. Веб-интерфейс чата (Next.js 14)

Каталог **`ai-chat-frontend/`** — одностраничное приложение (App Router), которое ходит на ваш **FastAPI на AWS** (не Railway).

| Требование задания | Где сделано |
|--------------------|-------------|
| Next.js 14+, App Router, TypeScript, Tailwind | `package.json`, `src/app/` |
| Ввод prompt, отправка на backend, показ ответа | `page.tsx`, `useChat.ts`, `api.ts` |
| **Streaming** через Fetch + `ReadableStream` + `TextDecoder` | `streamGenerateText` в `src/lib/api.ts` → `POST /generate/stream` |
| История текущей сессии | state в `useChat.ts` + **sessionStorage** (ключ в коде) |
| **AbortController** / кнопка Stop | `useChat.ts`, `PromptInput.tsx` |
| Ошибки 400 / 422 / 429 / 5xx и «backend недоступен» | `useChat.ts` (тексты как в ТЗ) |
| Markdown для ответов ассистента | `react-markdown` в `MessageBubble.tsx` |
| URL API из env | **`NEXT_PUBLIC_API_URL`** (`getApiUrl()` в `api.ts`) |

### Локальный запуск фронта

Нужен **Node.js LTS** (в PATH должны быть `node` и `npm`).

```bash
cd ai-chat-frontend
cp .env.example .env.local
# в .env.local: NEXT_PUBLIC_API_URL=http://ВАШ_AWS_IP:8000
npm install
npm run dev
```

Откройте [http://localhost:3000](http://localhost:3000). Бэкенд по умолчанию разрешает origin **`http://localhost:3000`** (`CORS_ORIGINS`).

### Production-сборка фронта

```bash
cd ai-chat-frontend
npm run lint
npm run build
npm start
```

### Деплой на Vercel (тот же репо, что и backend)

1. **New Project** → импорт GitHub-репозитория с этим кодом.
2. **Root Directory** → `ai-chat-frontend`.
3. **Environment Variables** → `NEXT_PUBLIC_API_URL` = `http://AWS_PUBLIC_IP:8000`.
4. Deploy → скопируйте URL вида `https://….vercel.app`.

Затем на **AWS** пересоберите и запустите контейнер API с обновлённым **`CORS_ORIGINS`** (см. **раздел 13** выше), включив URL Vercel.

### Документация только по фронту

Полное описание стека, архитектуры, переменных, ошибок и чеклиста видео — в **[ai-chat-frontend/README.md](ai-chat-frontend/README.md)**.

---

*Замените `SERVER_IP` / примеры URL в документации на актуальный публичный IP AWS и домен Vercel после деплоя.*
