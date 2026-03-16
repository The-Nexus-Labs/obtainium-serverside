# obtainium-serverside

📦 Small Python CLI for resolving Android app updates and optionally downloading APKs for automation workflows.

## ✨ What It Does

- compares desired apps with installed versions
- resolves the latest APK via a provider
- optionally downloads required APKs
- prints JSON with `updates` and `errors`

## 🔌 Providers

- `github`
- `loxone`

## ⚙️ Install

```bash
poetry install
```

## 🚀 Run

```bash
poetry run obtainium-serverside --config config.json --installed installed.json --download-dir downloads
```

Or:

```bash
poetry run python -m obtainium_serverside --config config.json --installed installed.json
```

## 🧾 Config

```json
{
  "apps": [
    {
      "app_id": "chat.simplex.app",
      "name": "SimpleX Chat",
      "provider": "github",
      "source_url": "https://github.com/simplex-chat/simplex-chat/releases",
      "provider_config": {
        "asset_regex": "^simplex-aarch64\\.apk$",
        "version_regex": "^v?(.+)$"
      }
    }
  ]
}
```

## 📱 Installed Input

```json
{
  "installed_apps": [
    {
      "app_id": "com.loxone.kerberos",
      "version": "16.2.1"
    }
  ]
}
```

If an app is missing, it is treated as not installed.

## 🧩 Provider Options

### `github`

- `asset_regex`: default `.*\.apk$`
- `version_regex`: default `^v?(.+)$`
- `version_source`: `auto | tag_name | name`
- `channel`: `stable | prerelease | any | release | beta`

### `loxone`

- `channel`: `release | beta`

## 🛠️ Dev

```bash
poetry run black --check .
poetry run mypy obtainium_serverside
poetry run pytest
```
