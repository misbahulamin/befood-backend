INVENTORY_TAG = 'Web Inventory'

ERROR_EXAMPLE = {
    'success': False,
    'message': 'Error description',
    'errors': {},
    'error_code': 'INVENTORY_ERROR',
}

INSUFFICIENT_STOCK_EXAMPLE = {
    'success': False,
    'message': 'পর্যাপ্ত stock নেই। Available Stock: 10 kg',
    'errors': {},
    'error_code': 'INSUFFICIENT_STOCK',
}

INSUFFICIENT_WALLET_EXAMPLE = {
    'success': False,
    'message': 'Admin Wallet-এ পর্যাপ্ত balance নেই।',
    'errors': {},
    'error_code': 'INSUFFICIENT_WALLET_BALANCE',
}
