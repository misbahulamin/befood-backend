"""Authenticated set-password for customers (social / phone unusable → usable)."""

from __future__ import annotations


class SetPasswordError(Exception):
    def __init__(self, message: str, code: str = 'SET_PASSWORD_ERROR'):
        self.message = message
        self.code = code
        super().__init__(message)


def set_customer_password(user, *, password: str, current_password: str | None = None) -> None:
    """
    Set a usable password on the authenticated customer.

    - Unusable password: current_password is not required.
    - Usable password: current_password must match.
    """
    if user.has_usable_password():
        if not current_password or not user.check_password(current_password):
            raise SetPasswordError(
                'Current password is required and must be correct.',
                code='CURRENT_PASSWORD_REQUIRED',
            )
    user.set_password(password)
    user.save(update_fields=['password'])
