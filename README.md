# Project 23 / «Безопасность в продакшене и лучшие практики»

## 1. Название и краткое описание

**GenAI API** — FastAPI-сервис для генерации текста дообученной моделью (LoRA). API дополнено базовыми production-механизмами: **ограничение частоты запросов (rate limiting)**, **валидация входных данных (Pydantic)** и **простой фильтр типичных паттернов prompt injection**. Репозиторий собирается в Docker, тестируется в GitHub Actions и может разворачиваться на AWS Ubuntu (SSH).

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

## 4. Пример успешного запроса (curl)

```bash
curl -X POST "http://SERVER_IP:8000/generate" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\":\"Hello\",\"max_tokens\":256,\"temperature\":0.7}"
```

Ожидается **HTTP 200** и JSON с полями `result`, `max_tokens`, `temperature`.

## 5. Примеры ошибок

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

## 6. Паттерны prompt injection (фильтруются)

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

## 7. Запуск локально (Python 3.10+)

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

## 8. Запуск через Docker

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

## 9. Запуск тестов

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Файлы: `tests/test_validation.py`, `tests/test_rate_limit.py`, `tests/test_security.py`.

## 10. Структура приложения (целевая схема задания)

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

## 11. Переменные окружения (инференс)

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

## 12. CI/CD и AWS

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
  genai-api
curl -f http://localhost:8000/health
```

С внешней машины: `http://AWS_PUBLIC_IP:8000/docs`. В **Security Group** EC2 должны быть разрешены **22** (SSH) и **8000** (HTTP API).

Секреты GitHub: `AWS_HOST`, `AWS_USER`, `AWS_SSH_KEY`, `AWS_PROJECT_PATH`, `MODEL_PATH`, `MODEL_NAME`; опционально `HF_WEIGHTS_REPO`, `HF_TOKEN`.

## 13. Известные ограничения

- Веса LoRA в публичном репозитории не хранятся (`model_weights/` пустой, только `.gitkeep`); для продакшена задайте `HF_WEIGHTS_REPO` / том с весами.
- Инференс с `transformers` + `peft` + `torch` требует ресурсов; первый ответ может быть долгим.
- Rate limit и фильтр injection — **базовый** уровень защиты, не заменяют WAF, аутентификацию и политики на уровне организации.

## 14. Критерии готовности (чеклист сдачи)

1. Код в GitHub; README и `requirements.txt` актуальны; Dockerfile собирается.
2. `pytest tests/` проходит.
3. API: **200** — корректный запрос; **400** — injection; **422** — валидация; **429** — превышение лимита.
4. Проверка на AWS: `curl http://localhost:8000/docs` на сервере и доступ с браузера по публичному IP.

---

*Ранее использовавшийся пример публичного URL в документации замените на актуальный IP/домен вашего инстанса после деплоя.*
