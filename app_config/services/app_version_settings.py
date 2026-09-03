from __future__ import annotations

from app_config.models import AppVersionSettings


def get_app_version_settings() -> AppVersionSettings:
    return AppVersionSettings.load()


def update_app_version_settings(
    *,
    latest_version: str | None = None,
    minimum_supported_version: str | None = None,
    play_store_url: str | None = None,
    app_store_url: str | None = None,
) -> AppVersionSettings:
    settings_obj = AppVersionSettings.load()
    if latest_version is not None:
        settings_obj.latest_version = latest_version
    if minimum_supported_version is not None:
        settings_obj.minimum_supported_version = minimum_supported_version
    if play_store_url is not None:
        settings_obj.play_store_url = play_store_url
    if app_store_url is not None:
        settings_obj.app_store_url = app_store_url
    settings_obj.save()
    return settings_obj
