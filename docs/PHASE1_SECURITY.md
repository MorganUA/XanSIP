# Фаза 1 — безопасность (runbook)

## 1.1 TLS (Caddy)

```bash
# В .env на сервере:
PUBLIC_WEB_DOMAIN=crm.example.com
PUBLIC_WEB_URL=https://crm.example.com
SESSION_HTTPS_ONLY=true
CADDY_EMAIL=admin@example.com

docker compose --profile tls up -d
```

Mini App Telegram требует HTTPS в `PUBLIC_WEB_URL`.

Self-signed (тест): `PUBLIC_WEB_DOMAIN=:443`, затем `PUBLIC_WEB_URL=https://185.192.23.225` (браузер предупредит о сертификате).

## 1.2 Production-режим

```bash
SIPCRM_ENV=production
SECRET_KEY=<32+ random>
BOT_API_SECRET=<24+ random>
WEB_ADMIN_PASSWORD=<strong>
WEB_ADMIN_PRIV_PASSWORD=<strong>
WEB_ADMIN_SUPPORT_PASSWORD=<strong>
REDIS_PASSWORD=<strong>
```

При `SIPCRM_ENV=production` API и bot **не стартуют** со слабыми секретами.

Для тестов: `SKIP_SECRET_VALIDATION=1` (только CI/dev).

## 1.3 Redis AUTH

```bash
# .env
REDIS_PASSWORD=your_redis_secret
REDIS_URL=redis://:your_redis_secret@redis:6379/0
```

Deploy (`deploy_server.py`) пересобирает `REDIS_URL` для Docker автоматически.

## 1.4 SSH deploy (ключ вместо пароля)

```bash
ssh-copy-id root@185.192.23.225
export DEPLOY_SSH_KEY=~/.ssh/id_ed25519
unset DEPLOY_PASSWORD
python3 scripts/deploy_server.py
```

## 1.5 Бэкапы

```bash
# Без секретов (по умолчанию):
python3 scripts/backup_full.py

# С .env + server.env:
BACKUP_INCLUDE_SECRETS=1 DEPLOY_PASSWORD='…' python3 scripts/backup_full.py

# GPG-шифрование архива:
BACKUP_GPG_PASSPHRASE='…' python3 scripts/backup_full.py
# → sipcrm-full-*.zip.gpg (plain zip удаляется)
```

## 1.6 Смена паролей Web CRM

1. Обновите `WEB_ADMIN_PASSWORD` / `WEB_ADMIN_PRIV_PASSWORD` / `WEB_ADMIN_SUPPORT_PASSWORD` в `.env`
2. Перезапустите API: `docker compose restart api`
3. `ensure_web_accounts` обновит хеши в `web_accounts`

## 1.7 Rate limit login

- 5 неудачных попыток с одного IP → блок 15 мин (HTTP 429)
- Redis keys: `login:fail:*`, `login:block:*`
- Успешный вход сбрасывает счётчик

## Чеклист после включения

- [ ] `curl -I https://PUBLIC_WEB_DOMAIN/api/health`
- [ ] Login Web CRM работает
- [ ] `docker compose exec redis redis-cli ping` без пароля → NOAUTH (если REDIS_PASSWORD задан)
- [ ] `python scripts/qa_ta_gate.py` → PASS
