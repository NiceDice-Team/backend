from django.http import JsonResponse
from django.views.defaults import page_not_found, server_error


def api_not_found(request, *args, **kwargs):
    return JsonResponse(
        {'type': 'client_error', 'errors': [{'code': 'not_found', 'detail': 'Not found.', 'attr': None}]},
        status=404,
    )


def not_found_handler(request, exception=None):
    if request.path.startswith('/api/'):
        return api_not_found(request)
    return page_not_found(request, exception)


def server_error_handler(request):
    if request.path.startswith('/api/'):
        return JsonResponse(
            {'type': 'server_error',
             'errors': [{'code': 'error', 'detail': 'A server error occurred.', 'attr': None}]},
            status=500,
        )
    return server_error(request)
