# AI Chat Frontend

Одностраничный чат на **Next.js 14 (App Router)** + **TypeScript** + **Tailwind CSS**, который обращается к вашему **FastAPI**-бэкенду на AWS.

## Ссылки (подставьте свои)

| Что | URL |
|-----|-----|
| **Backend (AWS)** | `http://YOUR_AWS_IP:8000` (пример: `http://16.16.24.138:8000`) |
| **Frontend (Vercel)** | `https://YOUR_PROJECT.vercel.app` — после деплоя |
| **Демо-видео** | _Добавьте ссылку на YouTube / Loom (30–60 с)_ |

## Скриншот / GIF

_После первого деплоя вставьте сюда скриншот чата или короткий GIF (можно через Vercel preview + запись экрана)._

## Стек

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- FastAPI backend (`/generate`, `/generate/stream`)
- Fetch API + `AbortController` для остановки генерации
- `react-markdown` для ответов ассистента

## Архитектура

```
src/
├── app/
│   ├── layout.tsx      — корневой layout, шрифт, метаданные
│   ├── page.tsx        — страница: useChat + ChatWindow + PromptInput
│   └── globals.css     — Tailwind
├── components/
│   ├── ChatWindow.tsx  — история, автопрокрутка, «Model is typing…»
│   ├── MessageBubble.tsx — user справа / assistant слева, markdown для assistant
│   └── PromptInput.tsx — ввод, Send / Stop, Enter / Shift+Enter
├── hooks/
│   └── useChat.ts      — состояние чата, streaming, sessionStorage, ошибки
└── lib/
    ├── api.ts          — getApiUrl, generateText, streamGenerateText (ReadableStream + TextDecoder)
    └── types.ts        — Message, Role, ChatError, …
```

**Streaming:** клиент читает `response.body` через `getReader()`, декодирует UTF-8 чанками и дописывает последнее сообщение ассистента.

> На бэкенде `/generate/stream` сначала вызывает модель целиком, затем отдаёт текст **по словам с паузой** (UX-поток). Нативный поток токенов из `transformers` в этом endpoint **не** используется — см. корневой `README.md` репозитория backend.

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `NEXT_PUBLIC_API_URL` | Базовый URL API **без** завершающего `/`, например `http://16.16.24.138:8000` |

Создайте локально:

```bash
cp .env.example .env.local
# отредактируйте .env.local — не коммитьте в Git
```

## Локальный запуск

Из каталога `ai-chat-frontend/`:

```bash
npm install
cp .env.example .env.local
# укажите NEXT_PUBLIC_API_URL=http://ВАШ_IP:8000
npm run dev
```

Откройте [http://localhost:3000](http://localhost:3000).

На backend в `CORS_ORIGINS` должен быть `http://localhost:3000` (это значение по умолчанию в `app/config.py`).

## Production build

```bash
npm run lint
npm run build
npm start
```

## Деплой (Vercel)

1. Залейте репозиторий (этот каталог или монорепо с root = `ai-chat-frontend` — настройте Root Directory в Vercel).
2. **Import** проекта в Vercel.
3. **Environment Variables:** `NEXT_PUBLIC_API_URL` = `http://YOUR_AWS_IP:8000`.
4. Deploy.

После деплоя добавьте origin фронта в **`CORS_ORIGINS`** на сервере и перезапустите Docker-контейнер API (см. корневой README).

## Обработка ошибок (UI)

| Ситуация | Сообщение |
|----------|-----------|
| Пустой prompt | кнопка **Send** неактивна |
| Сеть / backend недоступен | «Backend is unavailable. Please try again.» |
| HTTP 429 | «Rate limit exceeded. Please wait and try again.» |
| HTTP 422 | «Invalid input. Check prompt length and parameters.» |
| HTTP 400 | «Prompt rejected by security filter.» |
| HTTP 5xx | «Server error. Please try again later.» |
| Abort (Stop) | «Generation stopped.» (информационно, не как критическая ошибка) |

## Демо-видео (чеклист съёмки 30–60 с)

1. Открытый frontend.
2. Первый prompt → потоковый ответ.
3. Второй prompt → история диалога.
4. **Stop** или **Clear chat**.
5. По возможности кадр с ошибкой (например 429 после серии запросов).

Вставьте ссылку на видео в таблицу «Ссылки» вверху README.
