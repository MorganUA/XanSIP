# Документация SIP CRM

| Документ | Описание |
|----------|----------|
| [PROJECT_STATUS_REPORT.md](./PROJECT_STATUS_REPORT.md) | **Полный отчёт о состоянии проекта** — архитектура, риски, план исправлений, best practices |
| [PHASE1_SECURITY.md](./PHASE1_SECURITY.md) | **Фаза 1:** TLS, Redis AUTH, production mode, бэкапы |
| [PHASE2_CORRECTNESS.md](./PHASE2_CORRECTNESS.md) | **Фаза 2:** freeze групп, RBAC support, audit |
| [PHASE3_ARCHITECTURE.md](./PHASE3_ARCHITECTURE.md) | **Фаза 3:** routers, core/, guides JSON, миграции |
| [../.env.example](../.env.example) | Переменные окружения |

## Быстрые ссылки

- **Web CRM:** http://185.192.23.225:8000  
- **Деплой:** `scripts/deploy_server.py`  
- **QA gate:** `scripts/qa_ta_gate.py`  
- **Бэкап:** `scripts/backup_full.py`  

## Планируемые документы (фаза 4+)

- `RUNBOOK.md` — операционные процедуры (перезапуск, восстановление, ротация секретов)
- `adr/` — Architecture Decision Records
- `RBAC_MATRIX.md` — детальная матрица прав по каждому API-маршруту
