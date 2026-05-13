from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import render


def api_root(request):
    return render(request, 'index.html')


def api_404_handler(request, exception):
    if request.path.startswith('/api/'):
        return JsonResponse(
            {
                'type': 'client_error',
                'errors': [
                    {
                        'code': 'not_found',
                        'detail': 'Not found.',
                        'attr': None,
                    }
                ],
            },
            status=404,
        )
    return HttpResponseNotFound('Not Found')
