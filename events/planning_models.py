"""Annual planning, procurement and reviewable event imports."""
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

ZERO = Decimal('0')


class EventPlan(models.Model):
    event = models.OneToOneField('events.Meropriyatie', on_delete=models.CASCADE, related_name='plan')
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    month_start = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    month_end = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    organizer = models.CharField(max_length=300, blank=True, verbose_name='Организация / организатор')
    audience = models.CharField(max_length=300, blank=True, verbose_name='Целевая аудитория')
    participants_target = models.PositiveIntegerField(null=True, blank=True, verbose_name='План участников')
    participants_actual = models.PositiveIntegerField(null=True, blank=True, verbose_name='Факт участников')
    results = models.TextField(blank=True, verbose_name='Результаты и выводы')
    source_label = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(check=models.Q(month_end__gte=models.F('month_start')), name='event_plan_month_order')]


class EventBudget(models.Model):
    STATES = [('draft','Черновик'),('review','На согласовании'),('approved','Согласовано')]
    event = models.OneToOneField('events.Meropriyatie', on_delete=models.PROTECT, related_name='budget')
    allocated = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                   validators=[MinValueValidator(ZERO)], verbose_name='Лимит бюджета, ₽')
    funding_source = models.CharField(max_length=300, blank=True, verbose_name='Источник финансирования')
    status = models.CharField(max_length=15, choices=STATES, default='draft')
    updated_at = models.DateTimeField(auto_now=True)


class EventBudgetLine(models.Model):
    STATES = [('planned','Запланировано'),('ordered','Заказано'),('received','Получено'),('cancelled','Отменено')]
    budget = models.ForeignKey(EventBudget, on_delete=models.PROTECT, related_name='lines')
    title = models.CharField(max_length=200, verbose_name='Статья расходов / закупка')
    category = models.CharField(max_length=100, blank=True, verbose_name='Категория')
    unit = models.CharField(max_length=30, default='шт.', verbose_name='Единица измерения')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))], verbose_name='Плановое количество')
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(ZERO)], verbose_name='Плановая цена за единицу, ₽')
    purchased_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, validators=[MinValueValidator(ZERO)], verbose_name='Фактически получено')
    actual_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)], verbose_name='Стоимость закупки / обязательство, ₽')
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)], verbose_name='Оплачено, ₽')
    supplier = models.CharField(max_length=200, blank=True, verbose_name='Поставщик')
    document_number = models.CharField(max_length=100, blank=True, verbose_name='Номер счёта / договора')
    due_date = models.DateField(null=True, blank=True, verbose_name='Поставка до')
    status = models.CharField(max_length=20, choices=STATES, default='planned', verbose_name='Состояние закупки')
    note = models.TextField(blank=True, verbose_name='Примечание / ссылка на материал в карточке')
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def estimate(self):
        return (self.quantity * self.unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    class Meta:
        ordering = ['pk']
        constraints = [models.CheckConstraint(check=models.Q(paid_amount__lte=models.F('actual_amount')), name='event_payment_within_commitment')]


class EventBudgetApproval(models.Model):
    budget = models.ForeignKey(EventBudget, on_delete=models.PROTECT, related_name='approvals')
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class EventImportBatch(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    department = models.ForeignKey('accounts.Department', on_delete=models.PROTECT)
    source_label = models.CharField(max_length=300)
    rows = models.JSONField()
    committed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField(default=dict)


class EventImportRecord(models.Model):
    event = models.ForeignKey('events.Meropriyatie', on_delete=models.PROTECT, related_name='import_records')
    batch = models.ForeignKey(EventImportBatch, on_delete=models.PROTECT)
    key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
