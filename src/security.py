class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        response.setdefault(
            'Strict-Transport-Security',
            'max-age=31536000; includeSubDomains; preload'
        )

        response.setdefault('X-Content-Type-Options', 'nosniff')
        response.setdefault('X-Frame-Options', 'SAMEORIGIN')

        if request.path.startswith('/api/') or request.path.startswith('/admin/'):
            response.setdefault('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0')
            response.setdefault('Pragma', 'no-cache')
            response.setdefault('Expires', '0')

        return response
