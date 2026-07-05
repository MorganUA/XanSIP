# Phase 3 — Architecture

## Цели

1. Разделить монолитный `api/main.py` на роутеры.
2. Вынести общую конфигурацию в пакет `core/`.
3. Один источник миграций — только API startup.
4. Руководства — JSON в `data/guides/`, загрузчик в `services/guides_loader.py`.

## 3.1 API routers

```
api/
  main.py              # app factory, middleware, startup (миграции + web accounts)
  routers/
    pages.py           # /, /login, /mini, /api/health
    auth.py            # /api/auth/*
    dashboard.py       # /api/dashboard, /api/stats/sip-work*
    notifications.py   # /api/settings/notifications
    users.py           # /api/users/*
    sips.py            # /api/sips/*
    tickets.py         # /api/tickets/*
    groups.py          # /api/groups/*
  schemas/admin.py     # Pydantic request bodies
  serializers.py       # user/ticket serialization helpers
```

Существующие модули `routes_finance.py`, `routes_guides.py`, `routes_mini.py`, `routes_notion.py` подключены из `main.py` без изменений контрактов.

## 3.2 Слой core/

```
core/
  config.py              # Settings (единый источник)
  notification_config.py # уведомления Telegram
  finance_config.py      # финансы app_settings
```

Shim-файлы для обратной совместимости:

- `bot/config.py` → `core.config`
- `bot/services/notification_config.py` → `core.notification_config`
- `bot/services/finance_config.py` → `core.finance_config`

Новый код должен импортировать из `core.*`.

## 3.3 Миграции

| Компонент | До | После |
|-----------|-----|--------|
| `docker/entrypoint.sh` (bot) | `alembic upgrade head` | только wait DB + exec |
| `api/main.py` startup | `db.migrate.upgrade_head()` | без изменений (единственная точка) |
| `scripts/deploy_server.py` | extra `docker compose exec api alembic` | удалено |

## 3.4 Guides as JSON

```
data/guides/
  operations.json       # эксплуатационные руководства
  sip-integration.json  # Kolmisoft SIP guides
```

Редактирование: править JSON или запустить `python3 scripts/export_guides.py` после изменения legacy Python (если временно нужен экспорт).

Загрузка: `services/guides_loader.load_guide_bundle(name)`.

## Docker

В `Dockerfile.api` и `Dockerfile.bot` добавлены:

```
COPY core core
COPY data data
```

## Проверка

```bash
pytest tests/test_phase3_architecture.py tests/test_operation_guides.py tests/test_guides_contract.py -q
python3 scripts/qa_deep.py
```

## Следующие шаги (Phase 4)

- CI/CD pipeline (GitHub Actions)
- Перенос `routes_finance.py` и др. в `api/routers/`
- Полный переход импортов на `core.config` без shim
