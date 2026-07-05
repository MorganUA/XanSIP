## Summary

<!-- 1–3 пункта: что изменилось и зачем -->

## Test plan

- [ ] `python3 scripts/qa_ta_gate.py --unit-only`
- [ ] `docker compose exec api python scripts/qa_deep.py` (если затронут API/Mini App)
- [ ] Ручная проверка в Telegram / Web CRM (если UI)

## Deploy

- [ ] Не требуется
- [ ] `python3 scripts/deploy_server.py` после merge
