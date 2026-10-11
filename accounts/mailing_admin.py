from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.db.models import Count, Q
from django.core.paginator import Paginator
from .mailing_models import EmailCampaign, EmailDelivery
from .mailing_forms import ComposeForm, TestForm, ConfirmForm
from .mailing_service import prepare, stats, send_test, enqueue, cancel, MAIL_ERRORS, safe_error
from .mail_backend import FROM_EMAIL, config_path


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ('subject', 'status', 'audience', 'recipient_count', 'accepted_count', 'created_by', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('subject', 'audience', 'created_by__username')
    list_select_related = ('created_by',)
    list_per_page = 25
    actions = None

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            ui_total=Count('deliveries'), ui_sent=Count('deliveries', filter=Q(deliveries__status='sent')))

    @admin.display(description='Адресов')
    def recipient_count(self, obj):
        return obj.ui_total

    @admin.display(description='Принято SMTP')
    def accepted_count(self, obj):
        return obj.ui_sent

    def has_change_permission(self, request, obj=None):
        # Content and audience stay fixed after preview. Create a new draft to revise.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def can_send(self, request):
        return self.has_view_permission(request) and request.user.has_perm('accounts.send_emailcampaign')

    def get_urls(self):
        return [path('add/', self.admin_site.admin_view(self.compose), name='accounts_emailcampaign_add'),
                path('<int:pk>/change/', self.admin_site.admin_view(self.detail), name='accounts_emailcampaign_change')] + super().get_urls()

    def context(self, request, title):
        return {**self.admin_site.each_context(request), 'opts': self.model._meta, 'title': title,
                'media': self.media, 'sender': FROM_EMAIL, 'has_view_permission': True,
                'can_compose': self.has_add_permission(request)}

    def compose(self, request):
        if request.method not in ['GET', 'POST']:
            return HttpResponseNotAllowed(['GET', 'POST'])
        if not self.has_add_permission(request) or not self.has_view_permission(request):
            raise PermissionDenied
        form = ComposeForm(request.POST if request.method == 'POST' else None)
        if request.method == 'POST' and form.is_valid():
            try:
                campaign = prepare(form.cleaned_data, request.user)
            except ValueError as error:
                form.add_error(None, str(error))
            else:
                self.log_addition(request, campaign, 'Подготовлена рассылка; адресов: %s.' % campaign.deliveries.count())
                return redirect('admin:accounts_emailcampaign_change', pk=campaign.pk)
        context = self.context(request, 'Подготовить email-рассылку')
        context.update({'form': form, 'config_present': bool(settings.EMAIL_HOST)})
        return TemplateResponse(request, 'admin/accounts/emailcampaign/compose.html', context)

    def detail(self, request, pk):
        if request.method not in ['GET', 'POST']:
            return HttpResponseNotAllowed(['GET', 'POST'])
        if not self.has_view_permission(request):
            raise PermissionDenied
        campaign = get_object_or_404(EmailCampaign, pk=pk)
        test_form = TestForm(initial={'email': request.user.email})
        confirm_form = ConfirmForm()
        if request.method == 'POST':
            if not self.can_send(request):
                raise PermissionDenied
            action = request.POST.get('action')
            if action == 'test':
                test_form = TestForm(request.POST)
                if campaign.status != 'draft':
                    messages.error(request, 'Рассылка уже поставлена в очередь или закрыта.')
                    return redirect('admin:accounts_emailcampaign_change', pk=pk)
                if test_form.is_valid():
                    try:
                        send_test(campaign, test_form.cleaned_data['email'])
                    except MAIL_ERRORS as error:
                        messages.error(request, safe_error(error))
                    else:
                        self.log_change(request, campaign, 'Тест принят SMTP: ' + test_form.cleaned_data['email'])
                        messages.success(request, 'Тест принят SMTP. Проверьте письмо и папку «Спам».')
                    return redirect('admin:accounts_emailcampaign_change', pk=pk)
            elif action == 'queue':
                confirm_form = ConfirmForm(request.POST)
                if confirm_form.is_valid():
                    if enqueue(pk):
                        self.log_change(request, campaign, 'Рассылка поставлена в очередь.')
                        messages.success(request, 'Рассылка поставлена в очередь. Отправка идёт через фоновый обработчик.')
                    else:
                        messages.error(request, 'Сначала отправьте тест. Повторная постановка в очередь не выполняется.')
                    return redirect('admin:accounts_emailcampaign_change', pk=pk)
            elif action == 'cancel':
                if cancel(pk):
                    self.log_change(request, campaign, 'Ожидающие письма отменены.')
                    messages.success(request, 'Ожидающие письма отменены. Письмо, которое уже передаётся, может уйти.')
                else:
                    messages.error(request, 'Эта рассылка уже обработана или отменена.')
                return redirect('admin:accounts_emailcampaign_change', pk=pk)
            else:
                messages.error(request, 'Неизвестное действие.')
                return redirect('admin:accounts_emailcampaign_change', pk=pk)
        deliveries = campaign.deliveries.select_related('user').all()
        context = self.context(request, campaign.subject)
        context.update({'campaign': campaign, 'counts': stats(campaign), 'can_send': self.can_send(request),
                        'test_form': test_form, 'confirm_form': confirm_form,
                        'delivery_page': Paginator(deliveries, 50).get_page(request.GET.get('page')),
                        'config_present': bool(settings.EMAIL_HOST)})
        return TemplateResponse(request, 'admin/accounts/emailcampaign/detail.html', context)


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(admin.ModelAdmin):
    list_display = ('email', 'campaign', 'status', 'started_at', 'sent_at', 'error')
    list_filter = ('status', 'started_at')
    search_fields = ('email', 'campaign__subject')
    list_select_related = ('campaign', 'user')
    readonly_fields = ('email', 'campaign', 'user', 'status', 'started_at', 'sent_at', 'error')
    list_per_page = 50
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
