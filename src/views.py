from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render


def api_root(request):
    return render(request, 'index.html')


def sitemap_xml(request):
    backend_url = getattr(settings, 'BACKEND_URL', 'https://bgshop.work.gd').rstrip('/')
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{backend_url}/</loc>
  </url>
</urlset>
'''
    response = HttpResponse(xml, content_type='application/xml; charset=utf-8')
    response['Content-Security-Policy'] = "default-src 'none';"
    return response
