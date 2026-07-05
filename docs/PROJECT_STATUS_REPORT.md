# SIP CRM — отчёт о состоянии проекта

**Дата аудита:** 1 июля 2026  
**Версия стека:** Python 3.11 · FastAPI 0.111 · aiogram 3.7 · PostgreSQL 16 · Redis 7  
**Продакшен:** `http://185.192.23.225:8000` · путь на сервере `/opt/sipcrm`  
**Методология:** статический анализ кодовой базы, обзор инфраструктуры, результаты QA/TA gate (103 live-проверки, 84 pytest)

---

## 1. Резюме для руководства

SIP CRM — зрелый монорепозиторий, связывающий **Telegram-бот** (пользователи, группы колл-центра) и **Web CRM** (администрирование). Система развёрнута в Docker, имеет миграции БД, мультиаккаунтную авторизацию Web CRM, финансы USDT, Notion, колл-центр со SLA, руководства по эксплуатации и автоматизированный post-deploy QA.

| Показатель | Значение |
|------------|----------|
| Python-модулей | ~172 файла |
| API-маршрутов | ~77 |
| Модулей обработчиков бота | 16 |
| Таблиц БД | 13 |
| Миграций Alembic (head) | `e5f6a7b8c9d0` |
| Руководств по эксплуатации | 18 |
| Pytest (в Docker) | 84 passed |
| qa_deep (live) | 103 PASS / 0 FAIL |

**Общая оценка:** продукт **готов к эксплуатации** в текущем контуре, но для production-grade безопасности и сопровождения нужен **план hardening** (HTTPS, секреты, RBAC, CI/CD, мониторинг).

---

## 2. Назначение и границы системы

### 2.1 Что делает продукт

- **Пользователи (личный чат):** заявки об ошибках (`/err`, «🚨 Сообщить об ошибке»), SIP, баланс USDT, профиль, правила, руководства.
- **Группы колл-центра:** модерация при добавлении бота, `/err`, `/status`, SIP владельца группы.
- **Web CRM:** дашборд, колл-центр, пользователи, SIP, группы, финансы, Notion, журнал, уведомления, руководства.
- **Учётные записи Web:** `roof` (superadmin) + `admin01–05` + `support01–05`.

### 2.2 Вне scope репозитория

- Kolmisoft / телефония (только справочники и интеграционные гайды).
- Reverse proxy / TLS (не описан в репо — предполагается снаружи).
- CI/CD pipeline в GitHub/GitLab (отсутствует).

---

## 3. Архитектура

```
┌─────────────────┐     polling      ┌──────────────────┐
│  Telegram API   │◄─────────────────│  bot/main.py     │
└─────────────────┘                  │  :8080 internal  │
                                     └────────┬─────────┘
┌─────────────────┐  Session cookie          │
│  Браузер        │◄── FastAPI api/main.py ──┤
│  /, /login, /mini│    :8000 (host)         │
└─────────────────┘                          │
         │                                   │
         ▼                                   ▼
┌─────────────────────────────────────────────────────┐
│  PostgreSQL 16          Redis 7                      │
│  (users, tickets, finance, web_accounts, …)         │
└─────────────────────────────────────────────────────┘

Связь API ↔ Bot: X-Bot-Secret
  API → POST http://bot:8080/internal/webhook
  Bot → POST http://api:8000/api/tickets/create
```

### 3.1 Структура репозитория

| Каталог | Назначение |
|---------|------------|
| `api/` | FastAPI, SPA (`static/`), маршруты finance/notion/guides/mini |
| `bot/` | aiogram, handlers, FSM, webhook server |
| `db/` | SQLAlchemy models (10 файлов), repositories (8), migrate |
| `services/` | Общая бизнес-логика, web_auth, guides, notion, finance |
| `migrations/` | Alembic (6 ревизий) |
| `scripts/` | deploy, backup, QA gate, seed |
| `tests/` | 21 pytest-модуль |
| `docs/` | Документация (этот отчёт) |

### 3.2 Точки входа

| Сервис | Команда | Файл |
|--------|---------|------|
| API | `uvicorn api.main:app` | `Dockerfile.api` |
| Bot | `python -m bot.main` | `Dockerfile.bot` + `docker/entrypoint.sh` |
| Миграции | `alembic upgrade head` | bot entrypoint + API startup |

### 3.3 Зависимости образов

- `requirements-api.txt` → образ API (lean + pytest в образе).
- `requirements-bot.txt` → образ бота (без FastAPI).
- `requirements.txt` — полный lockfile для локальной разработки (~70 пакетов).

---

## 4. Состояние по доменам

### 4.1 База данных

**Таблицы (13):** `users`, `admin_logs`, `groups`, `sip_accounts`, `tickets`, `ticket_status_history`, `ticket_comments`, `app_settings`, `audit_events`, `user_accounts`, `usdt_wallets`, `deposits`, `web_accounts`.

**Цепочка миграций:**

| Ревизия | Содержание |
|---------|------------|
| `77896774ce40` | Начальные таблицы |
| `a1b2c3d4e5f6` | Service desk поля тикетов |
| `b2c3d4e5f6a7` | `app_settings` |
| `c3d4e5f6a7b8` | Метаданные групп, freeze |
| `d4e5f6a7b8c9` | Финансы, audit_events |
| `e5f6a7b8c9d0` | Web accounts |

**Замечание:** `WebAccount` не экспортирован в `db/models/__init__.py` — риск для autogenerate Alembic.

### 4.2 API (~77 маршрутов)

| Домен | Маршруты | Статус |
|-------|----------|--------|
| Auth | login, captcha, me, logout | Работает, мультиаккаунт |
| Dashboard / stats | KPI, экспорт CSV | Работает |
| Users | list, ban, role | Работает |
| SIP | CRUD, enable/disable | Работает |
| Tickets / service desk | очередь, take, status, create (bot) | Работает, SLA 3 мин |
| Groups | approve, freeze, ban, owner | Работает |
| Finance | config, wallets, deposits, balances | Работает |
| Notion | config, ledger sync | Опционально |
| Guides | operations + SIP integration | 18 + 8 гайдов |
| Mini App | `/api/mini/*` | HTTPS для prod |

### 4.3 Telegram-бот

- **16 handler-модулей**, ~97 функций-обработчиков.
- Middleware: DB session → auth (auto user) → ban → throttle (0.5 с, только private).
- FSM: `TicketFSM`, `FinanceFSM`.
- Центральная маршрутизация меню: `menu_dispatch.py`, `fsm_menu_guard.py`.
- Internal webhook: health + события тикетов для уведомлений в Telegram.

### 4.4 Web CRM (фронтенд)

- SPA: `api/static/index.html`, `app.js` (~97 KB), `app.css`.
- Разделы: dashboard, service-desk, users, sips, tickets, groups, finance, notion, guides, audit, notifications, system.
- Parity-тесты связывают `data-section` в HTML с руководствами и `SECTION_TITLES` в JS.

### 4.5 QA / тестирование

**Локальный gate (`scripts/qa_ta_gate.py`):**

1. `compileall` — синтаксис Python  
2. `pytest tests/` — 84 теста  
3. `import bot.main` — в образе API пропускается (нет aiohttp); на deploy проверяется в контейнере bot  
4. `qa_deep.py` — ~103 live-проверки  

**Области qa_deep:** Static, API, Security, Integration, WebUI, Unit, DB, Guides, Parity, Bot, Contract.

**CI/CD:** отсутствует в репозитории. QA запускается вручную и после `deploy_server.py`.

### 4.6 Деплой и бэкапы

| Скрипт | Назначение |
|--------|------------|
| `scripts/deploy_server.py` | SFTP + `docker compose` на сервере + post-deploy QA |
| `scripts/backup_full.py` | Код, `.env`, `pg_dump`, guides JSON → ZIP |
| `scripts/seed_web_accounts.py` | Ручной seed web-аккаунтов |

---

## 5. Сильные стороны

1. **Полный операционный контур** — бот + Web CRM + финансы + колл-центр + уведомления.
2. **Документированные руководства** — 18 operation guides + 8 SIP guides, parity с UI.
3. **Автоматизированный post-deploy QA** — 103 проверки на живом стеке.
4. **Разделение Docker-образов** — lean bot vs API.
5. **Мультиаккаунт Web CRM** — роли superadmin / admin / support с RBAC на критичных PUT.
6. **Миграции и healthchecks** — postgres, redis, api, bot.
7. **Аудит** — `audit_events`, `admin_logs`, журнал в Web CRM.
8. **Защита bot↔API** — shared secret на создание тикетов и webhook.

---

## 6. Проблемы и риски (приоритизация)

### P0 — Критично (безопасность / целостность данных)

| # | Проблема | Где | Риск |
|---|----------|-----|------|
| 1 | HTTP без TLS, `https_only=False` на сессиях | `api/main.py` | Перехват cookie сессии |
| 2 | Дефолтные секреты в коде (`change-me`, `change-me-bot-secret`) | `bot/config.py` | Компрометация при неполном `.env` |
| 3 | Redis без пароля | `docker-compose.yml` | Доступ при компрометации контейнера |
| 4 | Deploy/backup: root + password SSH, `AutoAddPolicy` | `deploy_server.py`, `backup_full.py` | MITM, утечка доступа |
| 5 | Бэкапы в открытом виде (`.env`, `postgres.sql`) | `backups/` | Концентрация всех секретов |
| 6 | Смена паролей в `.env` не обновляет хеши в БД | `services/web_auth.py` | «Сменили пароль — не работает» |

### P1 — Высокий (архитектура / надёжность)

| # | Проблема | Где | Риск |
|---|----------|-----|------|
| 7 | Монолитный `api/main.py` (~1020 строк) | `api/` | Сложность сопровождения |
| 8 | API импортирует `bot.*` | весь API | Невозможность изолированного деплоя API |
| 9 | Двойной запуск миграций (bot entrypoint + API startup) | deploy | Гонки при масштабировании |
| 10 | Нет CI/CD | — | Регрессии попадают в prod |
| 11 | Support-роль шире документации (ban, группы, SIP) | `api/main.py` | Избыточные права операторов |
| 12 | Freeze группы не блокирует `/err` и API create | `group_tickets.py`, `service_desk.py` | Обход модерации |

### P2 — Средний (качество / DX)

| # | Проблема | Где |
|---|----------|-----|
| 13 | Пустые `api/routers/`, `api/schemas/` | незавершённый рефакторинг |
| 14 | Дублирование audit: `admin_logs` + `audit_events` | db/models |
| 15 | Гайды в Python-коде (~45 KB) | `operation_guides.py` |
| 16 | `readme.md` — заметки, не архитектура | корень |
| 17 | Артефакты в репо (zip, jpg, backups) | корень |
| 18 | Pytest без изоляции БД, bypass `authenticate` | `tests/conftest.py` |
| 19 | Нет coverage, нет mutation-тестов API | tests/ |
| 20 | Слабая captcha, нет rate limit на login | `api/auth.py` |

### P3 — Низкий (улучшения)

| # | Проблема |
|---|----------|
| 21 | Webhook secret сравнивается через `==` в bot (не timing-safe) |
| 22 | Throttle только в private-чатах |
| 23 | OpenAPI доступен авторизованным пользователям |
| 24 | Production API-образ содержит pytest и tests/ |

---

## 7. План исправлений и улучшений

### Фаза 1 — Безопасность (1–2 недели)

| Задача | Действие | Критерий готовности |
|--------|----------|---------------------|
| 1.1 TLS | Caddy/nginx перед API, Let's Encrypt, `PUBLIC_WEB_URL=https://…` | Mini App включается, сессии `https_only=True` |
| 1.2 Секреты | Убрать дефолты из `bot/config.py`; fail-fast при `change-me` в prod | Старт падает без валидного `.env` |
| 1.3 Redis AUTH | `requirepass` + обновить `REDIS_URL` | redis-cli без пароля отклонён |
| 1.4 SSH | Ключи вместо password; non-root deploy user | `DEPLOY_PASSWORD` не используется |
| 1.5 Бэкапы | GPG-шифрование; исключить plaintext `.env` или отдельный vault | ZIP без открытых секретов |
| 1.6 Пароли web | `ensure_web_accounts`: обновлять hash при смене env | Смена `WEB_ADMIN_*_PASSWORD` работает после restart |
| 1.7 Login hardening | Rate limit (Redis): 5 попыток / 15 мин / IP; опционально fail2ban | qa_deep: новые security checks |

### Фаза 2 — Корректность и RBAC (1 неделя)

| Задача | Действие |
|--------|----------|
| 2.1 Freeze groups | Проверка `is_frozen` в `group_tickets.py` и `service_desk.create` |
| 2.2 Support RBAC | `_require_admin` на ban/role/groups/SIP если операторы только колл-центр |
| 2.3 WebAccount в `__init__.py` | Экспорт модели для Alembic metadata |
| 2.4 Единый audit | Миграция с `admin_logs` → `audit_events` или deprecation |

### Фаза 3 — Архитектура (2–4 недели)

| Задача | Действие |
|--------|----------|
| 3.1 Разбить `api/main.py` | Роутеры: users, tickets, groups, dashboard → `api/routers/` |
| 3.2 Слой `core/` | Вынести config, notification, finance_config из `bot/` в общий пакет |
| 3.3 Одна точка миграций | Только init-container или только API startup (не оба) |
| 3.4 Guides as data | `docs/guides/*.json` + loader; бэкап уже экспортирует JSON |

### Фаза 4 — Качество и CI (2 недели)

| Задача | Действие |
|--------|----------|
| 4.1 GitHub Actions | `pytest` + `compileall` на push; опционально `qa_deep` на staging |
| 4.2 Test DB | SQLite in-memory или testcontainers Postgres; fixtures с rollback |
| 4.3 API mutation tests | POST ban, approve group, confirm deposit с mock actor |
| 4.4 pytest-cov | Порог 60% на `services/`, `api/services/` |
| 4.5 Multi-role clients | Fixtures: roof, admin01, support01 в conftest |

### Фаза 5 — Observability (ongoing)

| Задача | Действие |
|--------|----------|
| 5.1 Structured logging | JSON logs, request_id middleware |
| 5.2 Metrics | Prometheus: request latency, ticket queue depth, SLA breach count |
| 5.3 Alerting | Uptime + container restart → Telegram admin chat |
| 5.4 Sentry | Exception tracking для API и bot |

---

## 8. Рекомендации (best practices)

### 8.1 Безопасность

- **Defense in depth:** TLS + secure cookies + rate limits + RBAC + IP allowlist для `/login`.
- **Secrets:** Docker Secrets или HashiCorp Vault; никогда не коммитить реальные пароли в `.env.example` — использовать `CHANGEME_*` плейсхолдеры.
- **Principle of least privilege:** support — только service-desk + read dashboard; admin — без назначения ролей.
- **Timing-safe compares:** `secrets.compare_digest` везде, включая `bot/webhook/server.py`.
- **Dependency scanning:** `pip-audit` в CI, ежемесячное обновление образов base.

### 8.2 Разработка

- **Conventional Commits** + PR review checklist (миграции, RBAC, guides parity).
- **Feature flags** для Notion, TEST_MODE, mini app.
- **ADR** (Architecture Decision Records) в `docs/adr/` для крупных решений.
- **Единый `core` пакет** вместо `api` → `bot` импортов.

### 8.3 Тестирование

- **Пирамида:** много unit → меньше integration → мало E2E.
- **Contract tests** для bot↔API JSON (уже частично есть).
- **Staging environment** с копией prod schema и анонимизированными данными.
- **`qa_ta_gate.py --strict`** перед каждым релизом.

### 8.4 Деплой

- **Immutable artifacts:** build образов в CI → push в registry → pull на сервере.
- **Health-based rollout:** ждать `healthy` вместо `sleep 25`.
- **Rollback:** тегировать образы по git SHA; `docker compose pull && up` на предыдущий тег.
- **Blue/green или rolling** при появлении второго инстанса.

### 8.5 Операции

- **Runbook** в `docs/RUNBOOK.md`: перезапуск, восстановление из бэкапа, ротация секретов.
- **RTO/RPO:** определить допустимое время простоя и потери данных.
- **Регулярные бэкапы:** cron `backup_full.py` + off-site копия.
- **Документация:** держать `operation_guides.py` синхронным с кодом (тест `test_guides_contract`).

---

## 9. Матрица RBAC Web CRM (фактическая vs документированная)

| Действие | support (док.) | support (факт) | admin | superadmin |
|----------|----------------|----------------|-------|------------|
| Колл-центр | ✓ | ✓ | ✓ | ✓ |
| Финансы PUT | ✗ | ✗ | ✓ | ✓ |
| Уведомления PUT | ✗ | ✗ | ✓ | ✓ |
| Ban пользователей | — | **✓** | ✓ | ✓ |
| Группы approve/ban | — | **✓** | ✓ | ✓ |
| SIP add/remove | — | **✓** | ✓ | ✓ |
| Назначение admin/superadmin | ✗ | ✗ | ✗ | ✓ |

**Рекомендация:** привести факт к документации (фаза 2.2) или обновить guide `admin-web-accounts`.

---

## 10. Покрытие тестами (gap analysis)

| Область | Покрытие | Пробел |
|---------|----------|--------|
| Guides, menu, parity | Хорошее | — |
| Ticket status, service desk queue | Хорошее | — |
| Finance parse, notification config | Среднее | confirm/reject deposit |
| API GET smoke | qa_deep | — |
| API mutations | **Нет** | ban, approve, finance PUT |
| Bot handlers runtime | **Нет** | FSM, /err, callbacks |
| Repositories | **Нет** | кроме parse_usdt_amount |
| web_auth authenticate/seed | **Нет** | только hash unit test |
| Mini App endpoints | **Нет** | только validate_init_data |
| Notion live API | **Нет** | только property builders |

---

## 11. Переменные окружения (справочник)

См. `.env.example`. Критичные для безопасности:

| Переменная | Назначение |
|------------|------------|
| `SECRET_KEY` | Подпись session cookie |
| `BOT_TOKEN` | Telegram API |
| `BOT_API_SECRET` | Bot ↔ API |
| `WEB_ADMIN_PASSWORD` | roof |
| `WEB_ADMIN_PRIV_PASSWORD` | admin01–05 |
| `WEB_ADMIN_SUPPORT_PASSWORD` | support01–05 |
| `POSTGRES_PASSWORD` | БД |
| `NOTION_TOKEN` | Интеграция (опционально) |

---

## 12. Команды для команды

```bash
# Локальный unit gate (без Docker)
python3 -m pytest tests/test_operation_guides.py tests/test_guides_contract.py tests/test_qa_deep.py -q

# Полный gate на сервере (в контейнере API)
docker compose exec -T api python scripts/qa_ta_gate.py

# Строгий режим (WARN = FAIL)
docker compose exec -T api python scripts/qa_ta_gate.py --strict

# Деплой
DEPLOY_PASSWORD='…' python3 scripts/deploy_server.py

# Полный бэкап
DEPLOY_PASSWORD='…' python3 scripts/backup_full.py
```

---

## 13. Заключение

Проект SIP CRM находится в **рабочем production-состоянии** с развитой предметной логикой (колл-центр, финансы, мультиаккаунт, руководства) и зрелым **post-deploy QA** (103 проверки). Главные точки роста — **безопасность периметра** (HTTPS, секреты, SSH), **согласованность RBAC**, **CI/CD** и **рефакторинг монолитного API**.

Рекомендуемый порядок: **Фаза 1 (безопасность)** → **Фаза 2 (RBAC/freeze)** → **Фаза 4 (CI)** → **Фаза 3 (архитектура)** параллельно с **Фазой 5 (observability)**.

---

*Отчёт сформирован автоматическим аудитом кодовой базы и результатов QA/TA gate. При изменении архитектуры обновляйте этот документ и `operation_guides.py`.*
