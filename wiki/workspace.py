from django.db.models import Q
from accounts.resources import fingerprint
from .models import WikiArticle, WikiRevision


def visible_articles(user):
    qs = WikiArticle.objects.select_related('department', 'author', 'updated_by', 'state')
    if user.is_director():
        return qs
    return qs.filter(Q(department__isnull=True) | Q(department_id=user.department_id))


def active_articles(qs):
    return qs.filter(Q(state__isnull=True) | Q(state__is_archived=False))


def can_edit(user, article):
    # Administrative Django access alone does not grant access to another department.
    return user.is_director() or user.pk == article.author_id or (user.is_head() and user.department_id and user.department_id == article.department_id)


def article_version(article):
    state = getattr(article, 'state', None)
    return fingerprint([article.pk, article.updated_at, state.updated_at if state else None,
                        state.is_archived if state else False])


def snapshot(article, user):
    return WikiRevision.objects.create(article=article, saved_by=user, title=article.title,
        content=article.content, category=article.category, department=article.department,
        is_pinned=article.is_pinned, tags=article.tags)
