SEARCH_TAG = 'Search'
SEARCH_ADMIN_TAG = 'Web Search'

SEARCH_SUCCESS_EXAMPLE = {
    'query': 'kacchi',
    'query_normalized': 'kacchi',
    'results': [
        {
            'type': 'food',
            'public_id': '11111111-1111-1111-1111-111111111111',
            'name': 'কাচ্চি বিরিয়ানি',
            'name_en': 'Kacchi Biryani',
            'short_description': '',
            'image_url': '',
            'price': None,
            'currency': 'BDT',
            'is_available': True,
            'deep_link_hint': 'food_detail',
        }
    ],
    'did_you_mean': None,
    'related': [],
}

SEARCH_DID_YOU_MEAN_EXAMPLE = {
    'query': 'kachci',
    'query_normalized': 'kachci',
    'results': [],
    'did_you_mean': 'কাচ্চি বিরিয়ানি',
    'related': [
        {
            'type': 'food',
            'public_id': '11111111-1111-1111-1111-111111111111',
            'name': 'কাচ্চি বিরিয়ানি',
            'name_en': 'Kacchi Biryani',
            'short_description': '',
            'image_url': '',
            'price': None,
            'currency': 'BDT',
            'is_available': True,
            'deep_link_hint': 'food_detail',
        }
    ],
}

SUGGESTIONS_EXAMPLE = {
    'query': 'ka',
    'query_normalized': 'ka',
    'results': [
        {
            'type': 'food',
            'public_id': '11111111-1111-1111-1111-111111111111',
            'name': 'কাচ্চি বিরিয়ানি',
            'name_en': 'Kacchi Biryani',
        }
    ],
}

POPULAR_EXAMPLE = {
    'results': [
        {'term': 'কাচ্চি', 'term_normalized': 'কাচ্চি', 'source': 'pin', 'count': None},
        {'term': 'chicken', 'term_normalized': 'chicken', 'source': 'analytics', 'count': 42},
    ]
}

ERROR_EXAMPLE = {
    'success': False,
    'message': 'Error description',
    'errors': {},
    'error_code': 'SEARCH_ERROR',
}
