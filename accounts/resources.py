"""Small shared helpers for material workspaces."""
import hashlib
import json
from django.core.paginator import Paginator
from accounts.models import Department


def safe_id(value):
    value = str(value or '')
    return int(value) if value.isascii() and value.isdecimal() and 0 < len(value) <= 18 else None


def departments_for(user):
    if user.is_director():
        return Department.objects.order_by('name')
    return Department.objects.filter(pk=user.department_id).order_by('name')


def paginate(request, queryset, size=20):
    page = Paginator(queryset, size).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return page, params.urlencode()


def fingerprint(values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()
