<h1 align="center">📦 obtainium-serverside</h1>

<p align="center">
Small Python CLI for resolving Android app updates and optionally downloading APKs for automation workflows.
</p>

> [!WARNING]
> **Vibe-coded project. No guarantees.**

## ✨ What it does

- compares desired apps with installed versions
- resolves the latest APK via a provider (or an exact pinned `version`, see below)
- optionally downloads required APKs
- prints JSON with `updates` and `errors`

## 🔌 Providers

- `fdroid`
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

### 📌 Version pinning

Each app may declare an optional `version`. When set, the resolver targets that
**exact** upstream version (for `github`, `fdroid`, and `loxone`) instead of the latest,
and plans an install whenever the installed version differs from the pin — including
holding at, or **downgrading** to, an older version. Pinned updates are flagged with
`"pinned": true` in the output. Omit `version` to keep the default latest behavior.

```json
{
  "apps": [
    {
      "app_id": "ws.xsoh.etar",
      "provider": "fdroid",
      "source_url": "https://f-droid.org/packages/ws.xsoh.etar/",
      "version": "1.0.55"
    }
  ]
}
```

## 📱 Installed input

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

## 🧩 Provider options

### `github`

- `asset_regex`: default `.*\.apk$`
- `version_regex`: default `^v?(.+)$`
- `version_source`: `auto | tag_name | name`
- `channel`: `stable | prerelease | any | release | beta`

### `fdroid`

- no provider-specific options

### `loxone`

- `channel`: `release | beta`

## 🛠️ Dev

```bash
poetry run black --check .
poetry run mypy obtainium_serverside
poetry run pytest
```
