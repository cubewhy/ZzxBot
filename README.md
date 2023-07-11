# zzxBot

## What's this

The source of LunarCN official bot

## How to start the bot

do `nb run -r` or `python3 bot.py`

## go-cqhttp config

> servers config only

```yaml
servers:
  - ws-reverse:
      universal: ws://127.0.0.1:8080/onebot/v11/ws/
      reconnect-interval: 3000
```
