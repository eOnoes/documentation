# Cyony Hermes DeepSeek Recovery Runbook

Use this when Cyony/Hermes is stuck on OpenRouter, out of OpenRouter credits, or failing with:

```text
HTTP 401: Missing Authentication header
Provider: openrouter
Model: deepseek/deepseek-v4-pro
```

Goal:

```text
Provider: deepseek
Model: deepseek-v4-pro or deepseek-v4-flash
Base URL: https://api.deepseek.com/v1
Not OpenRouter
```

## Important Paths

Host:

```bash
/root/agents/cyony
/root/agents/cyony/.hermes/config.yaml
/root/agents/cyony/.env
```

Inside Docker:

```bash
/opt/data
/opt/data/auth.json
/opt/data/.env
/opt/data/state.db
/opt/data/home
/opt/data/home/.hermes/config.yaml
```

Container:

```bash
hermes-agent-8eep-hermes-agent-1
```

## 1. SSH Into VPS

From PowerShell:

```powershell
ssh root@2.24.118.123
```

Then go to Cyony:

```bash
cd /root/agents/cyony
```

## 2. Confirm Container

```bash
docker ps | grep hermes
```

Expected container name:

```text
hermes-agent-8eep-hermes-agent-1
```

## 3. Back Up Files

```bash
cp .hermes/config.yaml .hermes/config.yaml.bak.before_deepseek
```

```bash
cp /var/lib/docker/volumes/e29d427e7c8ad445d170d4190327e7f911408294292f9b6f5b99209a3b85a297/_data/auth.json /var/lib/docker/volumes/e29d427e7c8ad445d170d4190327e7f911408294292f9b6f5b99209a3b85a297/_data/auth.json.bak.before_deepseek
```

```bash
cp /var/lib/docker/volumes/e29d427e7c8ad445d170d4190327e7f911408294292f9b6f5b99209a3b85a297/_data/state.db /var/lib/docker/volumes/e29d427e7c8ad445d170d4190327e7f911408294292f9b6f5b99209a3b85a297/_data/state.db.bak.before_deepseek
```

## 4. Set Primary Model Config

This changes Cyony's primary model from OpenRouter/Ollama/etc. to direct DeepSeek.

For V4 Pro:

```bash
perl -0pi -e 's/^model:\n  default: .*\n  provider: .*\n  base_url: .*/model:\n  default: deepseek-v4-pro\n  provider: deepseek\n  base_url: https:\/\/api.deepseek.com\/v1\n  key_env: DEEPSEEK_API_KEY/' .hermes/config.yaml
```

For V4 Flash:

```bash
perl -0pi -e 's/^model:\n  default: .*\n  provider: .*\n  base_url: .*/model:\n  default: deepseek-v4-flash\n  provider: deepseek\n  base_url: https:\/\/api.deepseek.com\/v1\n  key_env: DEEPSEEK_API_KEY/' .hermes/config.yaml
```

Verify:

```bash
sed -n '1,8p' .hermes/config.yaml
```

Expected:

```yaml
model:
  default: deepseek-v4-pro
  provider: deepseek
  base_url: https://api.deepseek.com/v1
  key_env: DEEPSEEK_API_KEY
```

## 5. Put DeepSeek Key In Hermes Data Env

If the key is not already present, add it without showing it on screen:

```bash
read -s -p "Paste DeepSeek key then press Enter: " K; echo; printf '\nDEEPSEEK_API_KEY=%s\n' "$K" >> /var/lib/docker/volumes/e29d427e7c8ad445d170d4190327e7f911408294292f9b6f5b99209a3b85a297/_data/.env; unset K
```

Also copy to Cyony home env if needed:

```bash
cp /var/lib/docker/volumes/e29d427e7c8ad445d170d4190327e7f911408294292f9b6f5b99209a3b85a297/_data/.env /root/agents/cyony/.env
```

Verify without printing the key:

```bash
docker exec hermes-agent-8eep-hermes-agent-1 sh -c 'grep -q "^DEEPSEEK_API_KEY=" /opt/data/.env && echo "DeepSeek key available"'
```

## 6. Register DeepSeek In Hermes Auth

Hermes may have the key in `.env` but still lack a DeepSeek credential in `auth.json`.

Patch `auth.json` without printing the key:

```bash
docker exec hermes-agent-8eep-hermes-agent-1 python3 -c "import json,time,uuid; p='/opt/data/auth.json'; d=json.load(open(p)); key=open('/opt/data/.env').read().split('DEEPSEEK_API_KEY=',1)[1].splitlines()[0].strip(); d.setdefault('credential_pool',{})['deepseek']=[{'id':'deepseek-'+uuid.uuid4().hex[:8],'label':'DEEPSEEK_API_KEY','auth_type':'api_key','priority':0,'source':'auth:DEEPSEEK_API_KEY','access_token':key,'base_url':'https://api.deepseek.com/v1','request_count':0,'last_status':'ok'}]; d['updated_at']=int(time.time()); json.dump(d,open(p,'w'),indent=2)"
```

Verify provider names only:

```bash
docker exec hermes-agent-8eep-hermes-agent-1 python3 -c "import json; d=json.load(open('/opt/data/auth.json')); print(list(d.get('credential_pool',{}).keys()))"
```

Expected:

```text
['kimi-coding', 'openrouter', 'deepseek']
```

## 7. Add Runtime Override Env

These help Hermes CLI/gateway prefer DeepSeek:

```bash
printf '\nHERMES_INFERENCE_PROVIDER=deepseek\nHERMES_INFERENCE_MODEL=deepseek-v4-pro\nDEEPSEEK_BASE_URL=https://api.deepseek.com/v1\n' >> /root/agents/cyony/.env
```

```bash
printf '\nHERMES_INFERENCE_PROVIDER=deepseek\nHERMES_INFERENCE_MODEL=deepseek-v4-pro\nDEEPSEEK_BASE_URL=https://api.deepseek.com/v1\n' >> /var/lib/docker/volumes/e29d427e7c8ad445d170d4190327e7f911408294292f9b6f5b99209a3b85a297/_data/.env
```

Use `deepseek-v4-flash` instead if that is the desired model.

## 8. Restart Container

```bash
docker restart hermes-agent-8eep-hermes-agent-1
```

Wait about 10 seconds.

Verify config inside container:

```bash
docker exec hermes-agent-8eep-hermes-agent-1 sh -c 'sed -n "1,8p" /opt/data/home/.hermes/config.yaml'
```

Verify direct DeepSeek works:

```bash
docker exec hermes-agent-8eep-hermes-agent-1 sh -c 'set -a; . /opt/data/.env; set +a; hermes -z "Reply only with pineapple" --provider deepseek -m deepseek-v4-pro'
```

Expected:

```text
pineapple
```

## 9. Telegram Reset Is Required

This was the missing Hermes-specific step.

Even after config/auth/env is fixed, Telegram sessions can keep stale provider metadata like:

```text
Provider: openrouter
Model: deepseek/deepseek-v4-pro
```

In Telegram, send:

```text
/reset
```

Approve the reset.

The reset card should now show:

```text
Model: deepseek-v4-pro
Provider: deepseek
```

Then test:

```text
Reply only with the word pineapple
```

Expected:

```text
pineapple
```

## 10. Verify Current Telegram Session In SQLite

If Cyony says the wrong provider but seems to work, verify actual billing/session metadata:

```bash
docker exec hermes-agent-8eep-hermes-agent-1 python3 -c "import sqlite3; con=sqlite3.connect('/opt/data/state.db'); print(con.execute(\"select rowid,id,model,billing_provider,billing_base_url,message_count from sessions where source='telegram' order by rowid desc limit 1\").fetchone())"
```

Good output should include:

```text
deepseek-v4-pro
deepseek
https://api.deepseek.com/v1
```

## What The Errors Mean

`HTTP 401: Missing Authentication header`

Usually means Hermes is trying to call a provider without an API key in the place it expects. Direct one-shot test with `set -a; . /opt/data/.env` proves whether the key and model are valid.

`Provider: openrouter` after changing config

Usually means Telegram session metadata is stale. Use `/reset` and approve.

`deepseek/deepseek-v4-pro via OpenRouter`

This is OpenRouter routing. Direct DeepSeek should look like:

```text
provider: deepseek
model: deepseek-v4-pro
base_url: https://api.deepseek.com/v1
```

## Safety Notes

Do not paste API keys into chat, screenshots, logs, or Markdown.

Prefer verification commands that only print:

```text
key ok
DeepSeek key available
```

Back up `config.yaml`, `auth.json`, and `state.db` before patching.

