"""Document registry with metadata editing and reversible archiving."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST, require_safe
from accounts.resources import safe_id, departments_for, paginate
from .models import Document, DocumentState
from .forms import DocumentForm
from .workspace import visible_documents, active_documents, document_version


def _user_can_access_documents(user):
    return user.is_director() or (user.is_head() and bool(user.department_id))


@login_required
@require_safe
def document_list_view(request):
    if not _user_can_access_documents(request.user):
        return HttpResponseForbidden('Документы доступны директору и руководителю своего отдела.')
    qs = visible_documents(request.user)
    archived = request.GET.get('archive') == '1'
    qs = qs.filter(state__is_archived=True) if archived else active_documents(qs)
    search = request.GET.get('search', '').strip()[:200]
    category = request.GET.get('category', '')
    department = request.GET.get('department', '')
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search) | Q(file__icontains=search))
    if category in dict(Document.CATEGORY_CHOICES):
        qs = qs.filter(category=category)
    if department:
        pk = safe_id(department)
        qs = qs.filter(department_id=pk) if pk else qs.none()
    sort = request.GET.get('sort', 'new')
    qs = qs.order_by('title', 'pk') if sort == 'title' else qs.order_by('-created_at', '-pk')
    page, query = paginate(request, qs)
    return render(request, 'documents/document_list.html', dict(documents=page, page_query=query,
        archived=archived, search=search, category=category, department_filter=department, sort=sort,
        category_choices=Document.CATEGORY_CHOICES, departments=departments_for(request.user)))


@login_required
@require_safe
def document_detail_view(request, pk):
    doc = get_object_or_404(visible_documents(request.user), pk=pk)
    return render(request, 'documents/document_detail.html', {'document': doc, 'version': document_version(doc),
        'archived': bool(getattr(doc, 'state', None) and doc.state.is_archived)})


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def document_create_view(request, pk=None):
    if not _user_can_access_documents(request.user):
        return HttpResponseForbidden('Нет доступа к документам.')
    doc = get_object_or_404(visible_documents(request.user).select_for_update(), pk=pk) if pk else None
    if doc and getattr(doc, 'state', None) and doc.state.is_archived:
        return HttpResponseForbidden('Сначала восстановите документ из архива.')
    version = document_version(doc) if doc else ''
    form = DocumentForm(request.POST or None, request.FILES or None, instance=doc, user=request.user)
    conflict = request.method == 'POST' and doc and request.POST.get('version') != version
    if conflict:
        form.add_error(None, 'Документ изменён другим пользователем. Обновите страницу и повторите правку.')
    elif request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        if not doc:
            saved.uploaded_by = request.user
        saved.save()
        state, _ = DocumentState.objects.get_or_create(document=saved)
        state.save()
        messages.success(request, 'Документ сохранён.')
        return redirect('document_detail', pk=saved.pk)
    return render(request, 'documents/document_form.html', dict(form=form, document=doc, version=version,
        title='Редактировать сведения' if doc else 'Добавить документ'), status=409 if conflict else 200)


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def document_delete_view(request, pk):
    doc = get_object_or_404(visible_documents(request.user).select_for_update(), pk=pk)
    version = document_version(doc)
    if request.method == 'POST':
        if request.POST.get('version') != version:
            return render(request, 'resources/conflict.html', status=409)
        state, _ = DocumentState.objects.get_or_create(document=doc)
        state.is_archived = True
        state.save()
        messages.success(request, 'Документ в архиве. Файл сохранён, документ можно восстановить.')
        return redirect('document_list')
    return render(request, 'documents/document_confirm_delete.html', {'document': doc, 'version': version})


@login_required
@require_POST
@transaction.atomic
def document_restore_view(request, pk):
    doc = get_object_or_404(visible_documents(request.user).select_for_update(), pk=pk)
    if request.POST.get('version') != document_version(doc):
        return render(request, 'resources/conflict.html', status=409)
    state, _ = DocumentState.objects.get_or_create(document=doc)
    state.is_archived = False
    state.save()
    messages.success(request, 'Документ восстановлен.')
    return redirect('document_detail', pk=pk)
