"""Customer wallet permission classes."""

from orders.api.permissions import IsVerifiedCustomer
from user_management.services.identity_verification import (
    IDENTITY_VERIFICATION_REQUIRED_WALLET_MESSAGE,
)


class IsVerifiedWalletCustomer(IsVerifiedCustomer):
    """
    Same identity OR-rule as IsVerifiedCustomer (email / phone / social),
    with wallet-scoped denial messaging for mobile UX.
    """

    message = IDENTITY_VERIFICATION_REQUIRED_WALLET_MESSAGE
