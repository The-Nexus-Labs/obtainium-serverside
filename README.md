<h1 align="center">📦 obtainium-serverside</h1>

<p align="center">
Small Python CLI for resolving app updates and optionally downloading release artifacts for automation workflows.
</p>

> [!WARNING]
> **Vibe-coded project. No guarantees.**

## ✨ What it does

- compares desired apps with installed versions
- resolves the latest release artifact via a provider (or an exact pinned `version`, see below)
- optionally downloads required APKs
- prints JSON with `updates` and `errors`

## 🔌 Providers

- `fdroid`
- `github`
- `http`
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
**exact** upstream version (for `github`, `fdroid`, `http`, and `loxone`) instead of the latest,
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

### `http`

Generic provider for apps distributed as ordinary files from an HTML page or JSON
release feed.

- `extractor`: `html_links | html_sections | html_json_attribute | json_entries`
  (default `html_links`)
- `entries_path`: dot path to the release list inside JSON payloads
- `download_url_path`: dot path to one or more download URLs
- `download_url_regex`: regex used to select/extract the download URL
- `version_path`: dot path to the version source
- `version_regex`: regex used to extract the version; a named `version` group is supported
- `release_name_path`: dot path to a release name
- `release_name_template`: Python format string, for example `JetBrains Toolbox {version}`
- `file_extension`: output/download extension, useful for compound extensions like `.tar.gz`
- `filters`: exact path/value filters for JSON-ish candidates
- `filters_regex`: regex path/value filters
- `exclude_regex`: regex path/value exclusions
- `prefer_false_path`: for latest resolution, prefer candidates where this path is falsey
- `version_match_strategy`: `exact | strip_trailing_parenthetical`

JetBrains Toolbox App for Linux via JetBrains' release API:

```json
{
  "apps": [
    {
      "app_id": "com.jetbrains.toolbox",
      "name": "JetBrains Toolbox",
      "provider": "http",
      "source_url": "https://data.services.jetbrains.com/products/releases?code=TBA&type=release",
      "provider_config": {
        "extractor": "json_entries",
        "entries_path": "TBA",
        "version_path": "build",
        "download_url_path": "downloads.linux.link",
        "release_name_template": "JetBrains Toolbox {version}",
        "file_extension": ".tar.gz"
      }
    }
  ]
}
```

### `loxone`

- compatibility alias implemented through `http`
- `channel`: `release | beta`
- `platform`: default `android`; also supports Loxone's structured download platforms such as `linux_x64`
- `file_extension`: default `.apk`

## 🛠️ Dev

```bash
poetry run black --check .
poetry run mypy obtainium_serverside
poetry run pytest
```
