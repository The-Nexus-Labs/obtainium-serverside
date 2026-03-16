# obtainium-serverside

Small controller-side Python utility for resolving Android app updates and downloading APKs for managed devices.

This project is a server-side analogue of Obtainium for Ansible and Termux workflows. It is intentionally small and provider-driven:

- inventory declares which Android apps are desired for a device
- automation collects installed package versions from the managed Android device
- `obtainium-serverside` resolves the latest available APKs for configured apps
- automation copies the APKs to the device and installs them with `pm install -r`

## Scope

The utility currently supports:

- a provider registry
- config-driven app definitions
- update planning by comparing installed and latest versions
- optional APK download during planning
- a generic `github` releases provider
- a custom `loxone` provider

## Installation

This repository uses Poetry.

```bash
poetry install
```

Run the CLI with Poetry:

```bash
poetry run obtainium-serverside --config config.json --installed installed.json --download-dir downloads
```

You can also run it as a module:

```bash
poetry run python -m obtainium_serverside --config config.json --installed installed.json
```

## CLI

Arguments:

- `--config`: JSON file describing apps that should be tracked
- `--installed`: JSON file describing apps currently installed on the target device
- `--download-dir`: optional directory where APKs for needed updates are downloaded

The command prints a JSON planning result with two top-level keys:

- `updates`
- `errors`

## Config Format

The config file is an object with an `apps` array:

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

## Installed Apps Format

The installed-apps input can be either a list or an object containing `installed_apps`.

Example:

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

If an app is missing from the installed list, the planner treats it as needing installation.

## Output Format

Example planner output:

```json
{
  "errors": [],
  "updates": [
    {
      "app_id": "com.loxone.kerberos",
      "download_url": "https://updatefiles.loxone.com/Android/Release/162215280.apk",
      "downloaded_apk_path": "/tmp/downloads/com.loxone.kerberos-16.2.2.apk",
      "installed_version": "16.2.1",
      "latest_version": "16.2.2",
      "name": "Loxone App",
      "provider": "loxone",
      "release_name": "Loxone App 16.2.2 for Android",
      "source_url": "https://www.loxone.com/enus/support/downloads/"
    }
  ]
}
```

## Providers

Providers live under `obtainium_serverside/providers/`.

Current provider registry:

- `github`
- `loxone`

## GitHub Provider

The `github` provider resolves APKs from GitHub releases for repositories that publish Android artifacts as release assets.

Supported provider config:

- `asset_regex`: regex that must match the release asset name. Default: `.*\.apk$`
- `version_regex`: regex used to extract the version from the chosen release tag or name. Default: `^v?(.+)$`
- `version_source`: one of `auto`, `tag_name`, or `name`. Default: `auto`
- `channel`: one of `stable`, `prerelease`, `any`, `release`, or `beta`. Default: `stable`

## Loxone Provider

The `loxone` provider scrapes the Loxone downloads page and selects the Android APK section.

Supported provider config:

- `channel: release`
- `channel: beta`

## Development

Run the local checks that CI runs:

```bash
poetry run black --check .
poetry run mypy obtainium_serverside
poetry run pytest
```

GitHub Actions runs the same checks on pull requests and pushes to `main`.
