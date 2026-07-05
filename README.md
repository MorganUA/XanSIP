# SIP CRM

Telegram-бот + Web CRM для колл-центра: заявки, SIP-линии, финансы, service desk, Mini App (Telegram WebApp) с WebRTC softphone.

## Стек

| Компонент | Технологии |
|-----------|------------|
| Bot | Python 3.11, aiogram 3, Redis FSM |
| API / Web CRM | FastAPI, asyncpg, SQLAlchemy 2 |
| Mini App | Vanilla JS, JsSIP (lazy) |
| Infra | Docker Compose, PostgreSQL 16, Redis 7 |

## Быстрый старт (локально)

```bash
cp .env.example .env   # заполните BOT_TOKEN, POSTGRES_*, SECRET_KEY
docker compose up -d --build
docker compose exec api python -m pytest tests/ -q
```

- Web CRM: http://localhost:8000  
- Mini App: http://localhost:8000/mini  

## Структура репозитория

```
api/           FastAPI, static Web CRM & Mini App, routers
bot/           Telegram bot handlers, keyboards, middlewares
core/          Shared config (settings, finance, notifications)
db/            SQLAlchemy models & repositories
migrations/    Alembic migrations (apply on API startup)
services/      Notion, guides loader, SIP trunk, audit
data/guides/   Operation & SIP integration guides (JSON)
scripts/       deploy, backup, QA gate, SSH setup
tests/         pytest contracts, RBAC, mini app, softphone
docs/          Architecture & security phases
```

## QA / деплой

```bash
./scripts/run_qa_local.sh
python3 scripts/qa_ta_gate.py
python3 scripts/setup_deploy_ssh.py --password 'ROOT_PASSWORD'  # один раз
python3 scripts/deploy_server.py
```

## Документация

См. [docs/README.md](docs/README.md).

## GitHub

```bash
# Один раз: ключ для push/pull
python3 scripts/setup_github_ssh.py
# → добавьте pubkey на https://github.com/settings/ssh/new
python3 scripts/setup_github_ssh.py --test
git push -u origin main
```

Remote: `git@github.com:bakaidesign1-a11y/XanSIP.git` · CI: `.github/workflows/ci.yml`

## Переменные окружения

Шаблон: [.env.example](.env.example). **Не коммитьте `.env`.**
