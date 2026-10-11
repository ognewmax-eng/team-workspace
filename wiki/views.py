"""Knowledge workspace. All reads and writes share the same department scope."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST, require_safe
from accounts.resources import safe_id, departments_for, paginate
from .models import WikiArticle, WikiArticleFile, WikiState, WikiFileState, WikiRevision
from .forms import WikiArticleForm, WikiArticleFileForm
from .workspace import visible_articles, active_articles, can_edit, article_version, snapshot
from .rendering import render_markdown


def archived(article):
    state = getattr(article, 'state', None)
    return bool(state and state.is_archived)


def editable(request, article, allow_archive=False):
    return can_edit(request.user, article) and (allow_archive or not archived(article))


def conflict(request):
    return render(request, 'resources/conflict.html', status=409)


def touch(article, user):
    article.updated_by = user
    article.save(update_fields=['updated_by', 'updated_at'])


@login_required
@require_safe
def wiki_list_view(request):
    scope = visible_articles(request.user)
    is_archive = request.GET.get('archive') == '1'
    qs = scope.filter(state__is_archived=True) if is_archive else active_articles(scope)
    search = request.GET.get('search', '').strip()[:200]
    category = request.GET.get('category', '')
    department = request.GET.get('department', '')
    tag = request.GET.get('tag', '').strip()[:100]
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(content__icontains=search) | Q(tags__icontains=search))
    if category in dict(WikiArticle.CATEGORY_CHOICES): qs = qs.filter(category=category)
    if department == 'common': qs = qs.filter(department__isnull=True)
    elif department and department != 'all':
        pk = safe_id(department)
        qs = qs.filter(department_id=pk) if pk else qs.none()
    if tag:
        # Match a complete comma-delimited tag, not accidental substrings.
        matches = [pk for pk, tags in qs.values_list('pk', 'tags') if tag.casefold() in [t.strip().casefold() for t in tags.split(',')]]
        qs = qs.filter(pk__in=matches)
    if request.GET.get('pinned') == '1': qs = qs.filter(is_pinned=True)
    sort = request.GET.get('sort', 'updated')
    ordering = {'title': ['-is_pinned', 'title', 'pk'], 'popular': ['-is_pinned', '-views_count', '-pk']}.get(sort, ['-is_pinned', '-updated_at', '-pk'])
    page, query = paginate(request, qs.order_by(*ordering))
    tags = sorted({t.strip() for raw in active_articles(scope).values_list('tags', flat=True) for t in raw.split(',') if t.strip()}, key=str.casefold)
    return render(request, 'wiki/wiki_list.html', dict(articles=page, page_query=query, archived=is_archive,
        search=search, category=category, department_filter=department, tag=tag, sort=sort,
        category_choices=WikiArticle.CATEGORY_CHOICES, departments=departments_for(request.user), all_tags=tags))


@login_required
@require_safe
def wiki_detail_view(request, article_id):
    article = get_object_or_404(visible_articles(request.user), pk=article_id)
    if request.method == 'GET': article.increment_views()
    html, toc = render_markdown(article.content)
    files = article.files.select_related('uploaded_by', 'state').all()
    is_editor = editable(request, article, allow_archive=True)
    if not is_editor: files = files.filter(Q(state__isnull=True) | Q(state__is_archived=False))
    revisions = article.revisions.select_related('saved_by')
    if not request.user.is_director():
        revisions = revisions.filter(Q(department__isnull=True) | Q(department_id=request.user.department_id))
    page, query = paginate(request, revisions, 10) if is_editor else (None, '')
    return render(request, 'wiki/wiki_detail.html', dict(article=article, rendered_content=html, toc=toc,
        files=files, can_edit=is_editor, archived=archived(article), version=article_version(article),
        revisions=page, page_query=query, file_form=WikiArticleFileForm()))


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def wiki_create_view(request, article_id=None):
    article = get_object_or_404(visible_articles(request.user).select_for_update(), pk=article_id) if article_id else None
    if article and not editable(request, article): return HttpResponseForbidden('Нет права редактировать эту статью.')
    version = article_version(article) if article else ''
    previous = {key: getattr(article, key) for key in ['title', 'content', 'category', 'department', 'is_pinned', 'tags']} if article else None
    form = WikiArticleForm(request.POST or None, request.FILES or None, instance=article, user=request.user)
    stale = request.method == 'POST' and article and request.POST.get('version') != version
    if stale:
        form.add_error(None, 'Статья изменилась. Скопируйте свои правки и обновите страницу.')
    elif request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        if article:
            WikiRevision.objects.create(article=article, saved_by=request.user, **previous)
            saved.updated_by = request.user
        else:
            saved.author = request.user
        saved.save()
        for upload in form.cleaned_data['files']:
            WikiArticleFile.objects.create(article=saved, file=upload, uploaded_by=request.user)
        messages.success(request, 'Статья сохранена.')
        return redirect('wiki_detail', article_id=saved.pk)
    return render(request, 'wiki/wiki_form.html', dict(form=form, article=article, version=version,
        title='Редактировать статью' if article else 'Новая статья'), status=409 if stale else 200)


wiki_update_view = wiki_create_view


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def wiki_delete_view(request, article_id):
    article = get_object_or_404(visible_articles(request.user).select_for_update(), pk=article_id)
    if not editable(request, article, allow_archive=True): return HttpResponseForbidden('Нет права архивировать статью.')
    if request.method == 'POST':
        if request.POST.get('version') != article_version(article): return conflict(request)
        state, _ = WikiState.objects.get_or_create(article=article)
        state.is_archived = True; state.save()
        messages.success(request, 'Статья в архиве. Текст, версии и вложения сохранены.')
        return redirect('wiki_list')
    return render(request, 'wiki/wiki_confirm_delete.html', {'article': article, 'version': article_version(article)})


@login_required
@require_POST
@transaction.atomic
def wiki_restore_view(request, article_id):
    article = get_object_or_404(visible_articles(request.user).select_for_update(), pk=article_id)
    if not editable(request, article, allow_archive=True): return HttpResponseForbidden()
    if request.POST.get('version') != article_version(article): return conflict(request)
    state, _ = WikiState.objects.get_or_create(article=article)
    state.is_archived = False; state.save()
    messages.success(request, 'Статья восстановлена.')
    return redirect('wiki_detail', article_id=article_id)


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def wiki_revision_view(request, article_id, revision_id):
    article = get_object_or_404(visible_articles(request.user).select_for_update(), pk=article_id)
    if not editable(request, article): return HttpResponseForbidden('История доступна редактору активной статьи.')
    revision = get_object_or_404(WikiRevision, pk=revision_id, article=article)
    if revision.department_id and not request.user.is_director() and revision.department_id != request.user.department_id:
        return HttpResponseForbidden('Версия относится к другому отделу.')
    if request.method == 'POST':
        if request.POST.get('version') != article_version(article): return conflict(request)
        snapshot(article, request.user)
        for key in ['title', 'content', 'category', 'department', 'is_pinned', 'tags']:
            setattr(article, key, getattr(revision, key))
        article.updated_by = request.user; article.save()
        messages.success(request, 'Текст и сведения восстановлены. Вложения не изменены.')
        return redirect('wiki_detail', article_id=article_id)
    html, _ = render_markdown(revision.content)
    return render(request, 'wiki/wiki_revision.html', {'article': article, 'revision': revision,
        'rendered_content': html, 'version': article_version(article)})


@login_required
@require_POST
@transaction.atomic
def wiki_add_file_view(request, article_id):
    article = get_object_or_404(visible_articles(request.user).select_for_update(), pk=article_id)
    if not editable(request, article): return HttpResponseForbidden()
    if request.POST.get('version') != article_version(article): return conflict(request)
    form = WikiArticleFileForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, 'wiki/wiki_upload_error.html', {'form': form, 'article': article}, status=400)
    attachment = form.save(commit=False); attachment.article = article; attachment.uploaded_by = request.user; attachment.save()
    touch(article, request.user)
    messages.success(request, 'Файл добавлен.')
    return redirect('wiki_detail', article_id=article_id)


@login_required
@require_POST
@transaction.atomic
def wiki_delete_file_view(request, file_id):
    attachment = get_object_or_404(WikiArticleFile, pk=file_id, article__in=visible_articles(request.user))
    article = get_object_or_404(visible_articles(request.user).select_for_update(), pk=attachment.article_id)
    if not editable(request, article): return HttpResponseForbidden()
    if request.POST.get('version') != article_version(article): return conflict(request)
    state, _ = WikiFileState.objects.get_or_create(attachment=attachment)
    state.is_archived = request.POST.get('action') != 'restore'; state.save()
    touch(article, request.user)
    messages.success(request, 'Файл скрыт из статьи. Его можно восстановить.' if state.is_archived else 'Файл восстановлен.')
    return redirect('wiki_detail', article_id=article.pk)


@login_required
@require_POST
def wiki_preview_view(request):
    text = request.POST.get('content', '')
    if len(text) > 200000: return JsonResponse({'error': 'Слишком длинный текст.'}, status=400)
    html, _ = render_markdown(text)
    return JsonResponse({'html': str(html)})
