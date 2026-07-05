# Фаза 2 — корректность и RBAC

## 2.1 Freeze групп

Замороженная группа (`is_frozen`) **не может** создавать заявки:

- Бот: `/err` и callback выбора ошибки — через `group_access_error()`
- API: `POST /api/tickets/create` — `ServiceDeskError 403`

Команды `/status` и `/sips` по-прежнему показывают сообщение о заморозке.

## 2.2 RBAC support vs admin

Модуль: `api/rbac.py` → `get_admin_actor`, `require_admin`.

| Действие | support | admin |
|----------|---------|-------|
| Колл-центр take/status | ✓ | ✓ |
| Ban, SIP, группы, роли | ✗ 403 | ✓ |

Проверка в QA: `Support blocked on user ban`, `Support blocked on SIP add`.

## 2.3 WebAccount в Alembic

`WebAccount` экспортирован в `db/models/__init__.py` для metadata autogenerate.

## 2.4 Audit

`admin_logs` **deprecated** — `log_admin_action()` пишет только в `audit_events`.
Исторические строки в `admin_logs` сохранены.

## Тесты

```bash
pytest tests/test_api_rbac.py tests/test_phase2_correctness.py -q
```
