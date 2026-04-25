# Project 23 — GenAI API (FastAPI + Docker + GitHub Actions → AWS)

## 1. Описание проекта

Публичный HTTP API для вывода дообученной языковой модели (LoRA поверх базовой модели с Hugging Face). Сервис отдаёт метаданные сервиса, проверку живости и эндпоинт генерации текста по промпту. Репозиторий рассчитан на сборку Docker-образа и автоматический деплой на AWS EC2 по SSH при каждом push в ветку `main`.

## 2. Архитектура

Цепочка развёртывания:

**модель → FastAPI → Docker → GitHub Actions → AWS EC2/VPS**

- Веса адаптера подставляются в каталог `MODEL_PATH` (в образе по умолчанию `/app/model_weights`): либо копированием при сборке (если веса небольшие), либо загрузкой при старте контейнера скриптом `scripts/download_weights.py` из Hugging Face Hub (см. ниже).
- CI: job `test` (pytest) → `build` (`docker build`) → `deploy` (SSH на EC2, `git pull`, пересборка и `docker run`).
- Секреты (SSH-ключ, токены HF и т.д.) задаются только в GitHub Actions Secrets и переменных окружения на сервере/в `docker run`, не хранятся в коде.

## 3. Переменные окружения

| Переменная | Назначение | Пример |
|------------|------------|--------|
| `MODEL_PATH` | Каталог с адаптером (LoRA) | `/app/model_weights` |
| `MODEL_NAME` | Имя модели в ответе API | `local-finetuned-model` |
| `HOST` | Хост uvicorn (в контейнере задан Dockerfile) | `0.0.0.0` |
| `PORT` | Порт приложения | `8000` |
| `ENV` | Окружение (`development` / `production`) | `production` |
| `BASE_MODEL_NAME` | Идентификатор базовой модели HF | `Qwen/Qwen2.5-1.5B-Instruct` |
| `BASE_MODEL_REVISION` | Ревизия базовой модели | `main` |
| `HF_WEIGHTS_REPO` | Репозиторий HF со снапшотом весов в `MODEL_PATH` | `org/my-lora-repo` |
| `HF_TOKEN` | Токен HF для приватных репозиториев | *(только secret)* |
| `USE_STUB` | `1` / `true` — принудительная заглушка без torch | `0` |

Полный список defaults см. в `app/config.py`.

## 4. Локальный запуск без Docker

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
set MODEL_PATH=model_weights
set MODEL_NAME=local-finetuned-model
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Без весов в `MODEL_PATH` сервис поднимется в режиме **заглушки** (ответы помечены `[stub:...]`).

## 5. Запуск через Docker

```bash
docker build -t genai-api .
docker run -p 8000:8000 ^
  -e MODEL_PATH=/app/model_weights ^
  -e MODEL_NAME=local-finetuned-model ^
  -e HF_WEIGHTS_REPO=your-org/your-weights-repo ^
  -e HF_TOKEN=your_hf_token ^
  genai-api
```

Проверка:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/
curl -X POST http://localhost:8000/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\": \"Объясни, что такое Docker\"}"
curl -X POST http://localhost:8000/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\": \"\"}"
```

Последний запрос должен вернуть **422** (пустой промпт).

## 6. Ссылка на деплой AWS

После успешного деплоя приложение доступно по адресу:

**http://16.16.24.138:8000**

Примеры:

- `http://16.16.24.138:8000/`
- `http://16.16.24.138:8000/health`

В Security Group инстанса должны быть открыты входящие **22** (SSH) и **8000** (HTTP API).

## 7. Описание CI/CD

Файл `.github/workflows/deploy.yml`:

1. **test** — checkout, Python 3.11, `pip install -r requirements.txt`, `pytest tests/ -v`.
2. **build** — `needs: test`, сборка образа `docker build -t genai-api .`.
3. **deploy** — `needs: build`, действие `appleboy/ssh-action`: клон/обновление репозитория в `AWS_PROJECT_PATH`, остановка старого контейнера, сборка на сервере, `docker run` с переменными из Secrets, проверка `curl -f http://localhost:8000/health`.

URL клона репозитория на сервере формируется как `https://github.com/${{ github.repository }}.git` (без хардкода owner/repo в репозитории).

Необходимые **GitHub Secrets**: `AWS_HOST`, `AWS_USER`, `AWS_SSH_KEY`, `AWS_PROJECT_PATH`, `MODEL_PATH`, `MODEL_NAME`; опционально `HF_WEIGHTS_REPO`, `HF_TOKEN` для загрузки весов при старте.

Артефакты для сдачи:

1. Ссылка на ваш GitHub-репозиторий (подставьте после публикации).
2. Публичный URL: **http://16.16.24.138:8000**
3. Ссылка на успешный run в GitHub Actions (вкладка Actions репозитория).
4. Пример запроса/ответа — см. раздел 8.

## 8. Пример запроса/ответа

**Запрос:**

```bash
curl -X POST http://16.16.24.138:8000/generate \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"Объясни, что такое Docker\", \"max_tokens\": 128}"
```

**Пример JSON-ответа** (в режиме заглушки в `response` будет префикс `[stub:...]`; с реальными весами — текст модели; `tokens_used` — целое число ≥ 1, для заглушки оценивается по длине ответа):

```json
{
  "prompt": "Объясни, что такое Docker",
  "response": "[stub:local-finetuned-model] Краткий ответ на запрос (первые символы промпта): 'Объясни, что такое Docker'…",
  "model": "local-finetuned-model",
  "tokens_used": 37
}
```

**GET /** (фрагмент):

```json
{
  "service": "GenAI API",
  "version": "1.0.0",
  "description": "Fine-tuned LLM inference API"
}
```

## 9. Известные ограничения

- Веса LoRA **не хранятся** в публичном репозитории (каталог `model_weights/` пустой, только `.gitkeep`). Для продакшена задайте `HF_WEIGHTS_REPO` и `HF_TOKEN` или смонтируйте том с весами на EC2.
- Полноценный инференс с `transformers` + `peft` + `torch` требует ресурсов (CPU возможен, GPU — для 4-bit по желанию); на слабом инстансе первый ответ может быть долгим.
- Загрузка весов из HF при старте зависит от сети и размера репозитория; `HEALTHCHECK` в Dockerfile даёт стартовый период **20s**.
- Репозиторий для `git clone` на сервере должен быть **доступен** с EC2 (публичный репозиторий или настройка deploy key — вне рамок базового ТЗ).
- Скрипты обучения в корне репозитория (`train_qlora.py` и др.) рассчитаны на расширенный набор пакетов; для них может понадобиться отдельное виртуальное окружение, не `requirements.txt` API.

## Подготовка AWS (однократно)

По SSH (ключ и IP из вашей инфраструктуры):

```bash
ssh -i evr_aws.pem ubuntu@16.16.24.138
sudo apt update
sudo apt install -y docker.io git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu
```

Выйти и зайти снова, затем `docker --version` и `mkdir -p /home/ubuntu/project_23`.
