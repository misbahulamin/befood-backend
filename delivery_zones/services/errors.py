class DeliveryZoneError(Exception):
    def __init__(self, message: str, code: str = 'DELIVERY_ZONE_ERROR'):
        super().__init__(message)
        self.code = code
