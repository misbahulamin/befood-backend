SERVICE_AREA_TAG = 'Service Areas'
SERVICE_AREA_ADMIN_TAG = 'Web Service Areas'

CHECK_AVAILABLE_EXAMPLE = {
    'verified': True,
    'service_available': True,
    'location_reliable': True,
    'warning_code': None,
    'customer_location': {
        'latitude': '22.356900',
        'longitude': '91.783200',
        'accuracy': '18.00',
        'location_name': 'GEC Circle, Chattogram',
    },
    'matched_service_area': {
        'public_id': '11111111-1111-1111-1111-111111111111',
        'name': 'Chawkbazar Hub',
        'latitude': '22.340100',
        'longitude': '91.830100',
        'radius_km': '5.00',
    },
    'nearest_service_area': None,
    'distance_km': '3.8000',
}

CHECK_UNAVAILABLE_EXAMPLE = {
    'verified': True,
    'service_available': False,
    'location_reliable': True,
    'warning_code': None,
    'customer_location': {
        'latitude': '22.390100',
        'longitude': '91.800500',
        'accuracy': None,
        'location_name': 'Halishahar, Chattogram',
    },
    'matched_service_area': None,
    'nearest_service_area': {
        'public_id': '11111111-1111-1111-1111-111111111111',
        'name': 'Chawkbazar Hub',
        'latitude': '22.340100',
        'longitude': '91.830100',
        'radius_km': '5.00',
    },
    'distance_km': '7.4000',
}

CHECK_LOW_ACCURACY_EXAMPLE = {
    'verified': True,
    'service_available': True,
    'location_reliable': False,
    'warning_code': 'LOW_LOCATION_ACCURACY',
    'customer_location': {
        'latitude': '22.356900',
        'longitude': '91.783200',
        'accuracy': '2500.00',
        'location_name': None,
    },
    'matched_service_area': {
        'public_id': '11111111-1111-1111-1111-111111111111',
        'name': 'Chawkbazar Hub',
        'latitude': '22.340100',
        'longitude': '91.830100',
        'radius_km': '5.00',
    },
    'nearest_service_area': None,
    'distance_km': '3.8000',
}

ERROR_EXAMPLE = {
    'success': False,
    'message': 'Error description',
    'errors': {},
    'error_code': 'SERVICE_AREA_ERROR',
}
