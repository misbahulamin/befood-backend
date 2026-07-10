import logging
import time

logger = logging.getLogger(__name__)


class SlowRequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration = time.perf_counter() - start
        if duration >= 2:
            logger.warning('Slow request method=%s path=%s status=%s duration=%.2fs', request.method, request.path, getattr(response, 'status_code', 'unknown'), duration)
        return response
