from django.conf import settings
def organization(request):
    return {'organization_name':settings.SITE_NAME,'organization_url':settings.SITE_URL}
