# Credential Index — Available to Hermes Agents

This file is non-secret. It tells agents what credentials exist and how to access them.

## How to retrieve credentials

From Hermes (or any agent with the proxy secret):

```
SECRET=$(cat ~/.openclaw/trello_proxy_secret)

# Get a credential value
curl -sk -X POST https://141.148.88.85/trello-api/creds/get \
  -H "X-Proxy-Agent-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{"name":"XIAOMI_API_KEY"}'
```

## Available Credentials

| Name | Type | What to pass in "name" field |
|------|------|---------|
| Trello API key | API key | `TRELLO_API_KEY` or `trello_api_key` |
| Trello OAuth token | OAuth token | `TRELLO_TOKEN` or `trello_token` |
| Trello proxy secret | HMAC secret | `TRELLO_PROXY_SECRET` or `trello_proxy_secret` |
| Xiaomi/MiniMax API key | API key | `XIAOMI_API_KEY` or `xiaomi_api_key` |
| Ollama API key | API key (local only) | `OLLAMA_API_KEY` or `ollama_api_key` |
| Telegram bot token | Bot token | `TELEGRAM_BOT_TOKEN` or `telegram_bot_token` |
| Gmail keyring password | Password | `GOG_KEYRING_PASSWORD` or `gog_keyring_password` |
| Google SA key | JSON file | `GCLOUD_SERVICE_ACCOUNT_KEY` or `gcloud_service_account_key` |

Names are case-insensitive — "TRELLO_API_KEY" and "trello_api_key" both work.

## Already On Hermes (no retrieval needed)

| What | Location/Command |
|------|-----------------|
| Trello proxy secret | `~/.openclaw/trello_proxy_secret` |
| Shared Gmail keyring | `~/.local/bin/shared-keyring-gog <email>` |
| List Gmail accounts | `~/.local/bin/shared-keyring-list --json` |
| Gmail accounts available | `jasonsant69@gmail.com` (calendar), `jasonsantpmp@gmail.com` (gmail modify) |
| Google Cloud SDK | `gcloud` — service account `milton@milton-bot-487614` activated |

## Trello API Proxy Usage

```
PROXY=https://141.148.88.85/trello-api
SECRET=$(cat ~/.openclaw/trello_proxy_secret)

# Read card (no auth)
curl -sk $PROXY/card/<shortLink>

# Add comment
curl -sk -X PUT $PROXY/add-comment \
  -H "X-Proxy-Agent-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{"cardId":"ID","agent":"Dwight","action":"Progress","text":"Working on this"}'

# Create card (auto-attributed with agent name + label)
curl -sk -X POST $PROXY/create-card \
  -H "X-Proxy-Agent-Secret: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{"name":"Task","listId":"ID","agent":"Dwight","source":"hermes","desc":"..."}'

# Move card
curl -sk -X PUT $PROXY/move-card \
  -H "X-Proxy-Agent-Secret: $SECRET" \
  -d '{"cardId":"ID","listId":"NEW_LIST_ID"}'

# List lists
curl -sk -X POST $PROXY/list-lists

# List labels
curl -sk -X POST $PROXY/list-labels
```

## Rules
- Never echo credentials in chat, Trello cards, or logs
- Prefer shared keyring for Gmail operations (`shared-keyring-gog`)
- Trello proxy secret is pre-deployed — use the local file, don't re-retrieve it
