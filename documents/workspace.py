from django.db.models import Q
from accounts.resources import fingerprint
from .models import Document


def visible_documents(user):
    qs = Document.objects.select_related('department', 'uploaded_by', 'state')
    if user.is_director():
        return qs
    if user.is_head() and user.department_id:
        return qs.filter(department_id=user.department_id)
    return qs.none()


def active_documents(qs):
    return qs.filter(Q(state__is_archived=False) | Q(state__isnull=True))


def document_version(doc):
    state = getattr(doc, 'state', None)
    return fingerprint([doc.pk, doc.title, doc.description, doc.department_id, doc.category,
                        doc.file.name, state.updated_at if state else None, state.is_archived if state else False])
