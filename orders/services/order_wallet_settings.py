from __future__ import annotations

from decimal import Decimal

from orders.models import OrderWalletSettings


def get_order_wallet_settings() -> OrderWalletSettings:
    return OrderWalletSettings.load()


def update_order_wallet_settings(
    *,
    min_wallet_balance_to_order: Decimal | None = None,
) -> OrderWalletSettings:
    settings_obj = OrderWalletSettings.load()
    if min_wallet_balance_to_order is not None:
        settings_obj.min_wallet_balance_to_order = min_wallet_balance_to_order
    settings_obj.save()
    return settings_obj
