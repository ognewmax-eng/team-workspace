"""Work profiles: own edits, active colleagues' public work information."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe
from .forms import UserProfileEditForm, UserWorkProfileForm
from .models import User, UserWorkProfile


WORK_FIELDS = ('about', 'responsibilities', 'skills', 'projects', 'work_schedule', 'workplace', 'contact_preferences')


def work_profile(user):
    # Viewing a blank profile must not write to the database.
    return UserWorkProfile.objects.filter(user=user).first() or UserWorkProfile(user=user)


def profile_page(request, member=None):
    member = member or request.user
    own = member.pk == request.user.pk
    profile = work_profile(member)
    blocks = [{'title': profile._meta.get_field(name).verbose_name, 'value': getattr(profile, name)} for name in WORK_FIELDS]
    filled = sum(bool(block['value'].strip()) for block in blocks)
    context = {'profile_user': member, 'work_profile': profile, 'profile_blocks': blocks,
               'own_profile': own, 'profile_filled': filled, 'profile_total': len(WORK_FIELDS),
               'profile_percent': round(filled * 100 / len(WORK_FIELDS))}
    if own:
        from tasks.workspace import visible_tasks
        tasks = visible_tasks(request.user).filter(assigned_to=member, is_archived=False)
        context['profile_stats'] = tasks.aggregate(
            assigned=Count('pk', filter=Q(status='assigned'), distinct=True),
            in_progress=Count('pk', filter=Q(status='in_progress'), distinct=True),
            pending=Count('pk', filter=Q(status='pending'), distinct=True),
            completed=Count('pk', filter=Q(status='completed'), distinct=True))
        context['profile_tasks'] = tasks.exclude(status='completed').order_by('deadline', '-pk')[:5]
    return render(request, 'accounts/profile.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def edit_profile(request):
    profile = work_profile(request.user)
    form = UserProfileEditForm(request.POST if request.method == 'POST' else None, instance=request.user)
    work_form = UserWorkProfileForm(request.POST if request.method == 'POST' else None, instance=profile)
    if request.method == 'POST':
        valid = form.is_valid()
        work_valid = work_form.is_valid()
        if valid and work_valid:
            with transaction.atomic():
                # The owner is always the logged-in user; POST cannot change it.
                form.save()
                work_form.instance.user = request.user
                work_form.save()
            messages.success(request, 'Профиль обновлён.')
            return redirect('profile')
        messages.error(request, 'Исправьте отмеченные поля. Изменения пока не сохранены.')
    return render(request, 'accounts/profile_edit.html', {'form': form, 'work_form': work_form})


@login_required
@require_safe
def colleague_profile(request, user_id):
    member = get_object_or_404(User.objects.select_related('department'), pk=user_id, is_active=True)
    return profile_page(request, member)


@login_required
@require_safe
def colleagues(request):
    query = request.GET.get('search', '').strip()[:200]
    people = User.objects.filter(is_active=True).select_related('department', 'work_profile').order_by('last_name', 'first_name', 'username')
    if query:
        people = people.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) |
            Q(username__icontains=query) | Q(position__icontains=query) | Q(department__name__icontains=query) |
            Q(work_profile__skills__icontains=query) | Q(work_profile__responsibilities__icontains=query) |
            Q(work_profile__projects__icontains=query))
    return render(request, 'accounts/colleagues.html', {'people_page': Paginator(people, 24).get_page(request.GET.get('page')), 'search': query})
