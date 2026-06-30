<h1 align="center">📦 obtainium-serverside</h1>

<p align="center">
Small Python CLI for resolving app updates and optionally downloading release
artifacts for automation workflows.
</p>

> [!WARNING]
> **Vibe-coded project. No guarantees.**

## ✨ What it does

- compares desired apps with installed versions
- resolves the latest release artifact via a provider (or an exact pinned `version`, see below)
- optionally downloads required release artifacts
- prints JSON with `updates` and `errors`

## 🔌 Providers

- `fdroid`
- `github`
- `http`

## ⚙️ Install

```bash
poetry install
```

## 🚀 Run

```bash
poetry run obtainium-serverside --config config.json --installed installed.json \
  --download-dir downloads
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
**exact** upstream version (for `github`, `fdroid`, and `http`) instead of the latest,
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
- `download_url`: static download URL, useful with a separate `version` resolver
- `release_name_path`: dot path to a release name
- `release_name_template`: Python format string, for example `JetBrains Toolbox {version}`
- `file_extension`: output/download extension, useful for compound extensions like `.tar.gz`
- `filters`: exact path/value filters for JSON-ish candidates
- `filters_regex`: regex path/value filters
- `exclude_regex`: regex path/value exclusions
- `prefer_false_path`: for latest resolution, prefer candidates where this path is falsey
- `version_match_strategy`: `exact | strip_trailing_parenthetical`

The HTTP provider can also resolve the latest version independently from artifact
resolution through `provider_config.version`. This is useful for projects where a
small JSON endpoint or page contains the current version, while the installer URL
is stable or no artifact download is needed.

- `version.extractor`: `json_path | regex`
- `version.source_url`: URL to fetch for the version check; defaults to `source_url`
- `version.path`: dot path for `json_path`
- `version.pattern`: regex for `regex`; a named `version` group is supported

TLauncher version-only check via its app config JSON:

```json
{
  "apps": [
    {
      "app_id": "org.tlauncher.tlauncher",
      "name": "TLauncher",
      "provider": "http",
      "source_url": "https://tlauncher.org/",
      "provider_config": {
        "version": {
          "extractor": "json_path",
          "source_url": "https://repo.tlauncher.org/tlauncher-sources/prod/release/tlauncher/appConfig.json",
          "path": "appVersion"
        }
      }
    }
  ]
}
```

For a webpage regex version check:

```json
{
  "version": {
    "extractor": "regex",
    "source_url": "https://example.com/releases",
    "pattern": "Version (?P<version>\\d+\\.\\d+\\.\\d+)"
  }
}
```

If downloads are needed with a separate version resolver, add either the existing
HTTP artifact settings or a static `download_url`:

```json
{
  "download_url": "https://tlauncher.org/installer-linux",
  "file_extension": ".sh"
}
```

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

Loxone App for Android via the Loxone downloads page:

```json
{
  "apps": [
    {
      "app_id": "com.loxone.kerberos",
      "name": "Loxone App",
      "provider": "http",
      "source_url": "https://www.loxone.com/enus/support/downloads/",
      "provider_config": {
        "extractor": "html_json_attribute",
        "html_class": "loxone-software-download-root",
        "html_attr": "data-config",
        "html_attr_encoding": "base64",
        "entries_path": "config",
        "filters": {
          "application": "app",
          "type": "release"
        },
        "prefer_false_path": "archived",
        "version_path": "version",
        "version_match_strategy": "strip_trailing_parenthetical",
        "download_url_path": "allVersions.groups.downloads.url",
        "download_url_regex": "https://updatefiles\\.loxone\\.com/Android/Release/.*\\.apk$",
        "release_name_path": "title",
        "append_version_to_release_name": true,
        "file_extension": ".apk"
      }
    }
  ]
}
```

For the Loxone Linux `.deb`, use the same config with:

```json
{
  "download_url_regex": "https://updatefiles\\.loxone\\.com/linux/Release/.*\\.deb$",
  "file_extension": ".deb"
}
```

## 🛠️ Dev

```bash
poetry run black --check .
poetry run mypy obtainium_serverside
poetry run pytest
```
