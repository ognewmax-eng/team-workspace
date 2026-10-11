"""
Views для управления расписанием и календарем.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count
from datetime import datetime, date
from calendar import month_name
from .models import ScheduleEvent, Association, Lesson, ScheduleTemplate
from .forms import ScheduleEventForm, LessonForm, ScheduleTemplateForm
from accounts.models import Department
from accounts.google_calendar import sync_schedule_event_to_google_calendar, delete_schedule_event_from_google_calendar
from datetime import datetime, timedelta
import json
from django.http import HttpResponse
from io import BytesIO
from .planner import visible_events, visible_associations, can_edit_event
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


@login_required
def schedule_main_view(request):
    from .planner import calendar_context
    return render(request, 'schedule/calendar.html', calendar_context(request))


@login_required
def schedule_calendar_view(request):
    from .planner import calendar_context
    return render(request, 'schedule/calendar.html', calendar_context(request))


@login_required
def schedule_list_view(request):
    from .planner import calendar_context, calendar_data
    from django.core.exceptions import ValidationError
    context = calendar_context(request)
    try:
        context['agenda_items'] = calendar_data(request)
    except ValidationError as exc:
        context['agenda_error'] = '; '.join(exc.messages)
        context['agenda_items'] = []
    return render(request, 'schedule/schedule_list.html', context)


@login_required
def schedule_event_detail_view(request, event_id):
    """
    Детальная страница события.
    """
    # Оптимизация: используем select_related и prefetch_related
    event = get_object_or_404(
        visible_events(request.user).select_related('department', 'created_by').prefetch_related('participants'),
        id=event_id
    )
    
    context = {
        'event': event,
        'can_edit_event': can_edit_event(request.user, event),
    }
    return render(request, 'schedule/event_detail.html', context)


@login_required
def schedule_event_create_view(request):
    """
    Создание нового события в расписании.
    """
    if request.method == 'POST':
        form = ScheduleEventForm(request.POST, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            with transaction.atomic():
                event.save()
                form.save_m2m()  # Сохранение many-to-many полей (participants)
            
            # Синхронизация с Google Calendar
            try:
                sync_schedule_event_to_google_calendar(event)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка синхронизации события с Google Calendar: {str(e)}")
            
            messages.success(request, 'Событие успешно создано.')
            return redirect('schedule_main')
    else:
        start = timezone.localtime().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        initial = {'start_time': start, 'end_time': start + timedelta(hours=1), 'event_type': 'meeting'}
        if request.user.department_id: initial['department'] = request.user.department_id
        for field, key in [('start_time', 'start'), ('end_time', 'end')]:
            try:
                initial[field] = datetime.strptime(request.GET.get(key, ''), '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        form = ScheduleEventForm(user=request.user, initial=initial)

    return render(request, 'schedule/event_form.html', {'form': form, 'title': 'Создать событие'})


@login_required
def schedule_event_update_view(request, event_id):
    """
    Редактирование события.
    """
    event = get_object_or_404(ScheduleEvent, id=event_id)
    
    if not can_edit_event(request.user, event):
        from django.http import Http404
        raise Http404

    if request.method == 'POST':
        form = ScheduleEventForm(request.POST, instance=event, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                form.save()
            
            # Синхронизация с Google Calendar
            try:
                sync_schedule_event_to_google_calendar(event)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка синхронизации события с Google Calendar: {str(e)}")
            
            messages.success(request, 'Событие обновлено.')
            return redirect('schedule_main')
    else:
        form = ScheduleEventForm(instance=event, user=request.user)

    return render(request, 'schedule/event_form.html', {'form': form, 'event': event, 'title': 'Редактировать событие'})


@login_required
def schedule_events_json(request):
    from .planner import calendar_data
    from django.core.exceptions import ValidationError
    try:
        response = JsonResponse(calendar_data(request), safe=False)
        response['Cache-Control'] = 'private, no-store'
        return response
    except ValidationError as exc:
        return JsonResponse({'error': '; '.join(exc.messages)}, status=400)


# ==================== Расписание занятий ====================

@login_required
def lessons_schedule_view(request):
    from .planner import lessons_context
    return render(request, 'schedule/lessons_schedule.html', lessons_context(request))


@login_required
def lesson_create_view(request):
    from .planner import create_lesson
    return create_lesson(request)


@login_required
def lesson_update_view(request, lesson_id):
    from .planner import update_lesson
    return update_lesson(request, lesson_id)


@login_required
def lesson_delete_view(request, lesson_id):
    from .planner import delete_lesson
    return delete_lesson(request, lesson_id)


@login_required
def lesson_move_view(request, lesson_id):
    from .planner import move_lesson
    return move_lesson(request, lesson_id)


@login_required
def create_template_from_schedule_view(request):
    from .planner import create_template
    return create_template(request)


@login_required
def apply_template_view(request):
    from .planner import apply_template
    return apply_template(request)


@login_required
def clear_week_view(request):
    from .planner import clear_schedule
    return clear_schedule(request)


@login_required
def delete_template_view(request, template_id):
    from .planner import delete_template
    return delete_template(request, template_id)


# ==================== Экспорт расписания занятий ====================

@login_required
def export_lessons_schedule_pdf(request):
    """
    Экспорт расписания занятий в PDF.
    """
    user = request.user
    association_id = request.GET.get('association')
    
    if not association_id:
        messages.error(request, 'Не выбрано объединение')
        return redirect('lessons_schedule')
    
    if user.is_director():
        try:
            association = visible_associations(user).get(id=association_id)
        except (Association.DoesNotExist, ValueError, OverflowError):
            messages.error(request, 'Объединение не найдено')
            return redirect('lessons_schedule')
    else:
        try:
            association = visible_associations(user).get(id=association_id)
        except (Association.DoesNotExist, ValueError, OverflowError):
            messages.error(request, 'Объединение не найдено или у вас нет доступа')
            return redirect('lessons_schedule')
    
    # Получаем занятия для текущей недели
    lessons = Lesson.objects.filter(
        association=association,
        is_template=False
    ).order_by('weekday', 'start_time')
    
    # Определяем текущую неделю
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # Регистрируем шрифт с поддержкой кириллицы
    cyrillic_font_name = 'DejaVuSans'
    cyrillic_font_bold_name = 'DejaVuSans-Bold'
    
    # Пытаемся зарегистрировать шрифты DejaVu Sans для поддержки кириллицы
    font_registered = False
    
    # Сначала проверяем, не зарегистрирован ли уже шрифт
    if cyrillic_font_name in pdfmetrics.getRegisteredFontNames():
        font_registered = True
    else:
        # Пытаемся найти шрифт в системе
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/TTF/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/TTF/LiberationSans-Regular.ttf',
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    # Регистрируем обычный шрифт
                    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path, 'UTF-8'))
                    # Пытаемся зарегистрировать жирный шрифт
                    bold_path = font_path.replace('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf')
                    if not os.path.exists(bold_path):
                        # Пробуем альтернативные пути для жирного шрифта
                        bold_path = font_path.replace('Regular', 'Bold')
                    if os.path.exists(bold_path):
                        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold_path, 'UTF-8'))
                    font_registered = True
                    break
                except Exception as e:
                    # Логируем ошибку, но продолжаем поиск
                    continue
    
    # Если не удалось зарегистрировать шрифт с кириллицей, используем стандартные
    # (но они не будут отображать кириллицу правильно)
    if not font_registered:
        cyrillic_font_name = 'Helvetica'
        cyrillic_font_bold_name = 'Helvetica-Bold'
    
    # Создаем PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), 
                           rightMargin=2*cm, leftMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    # Стили с поддержкой кириллицы
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=cyrillic_font_bold_name,
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=1  # Центрирование
    )
    
    normal_style = ParagraphStyle(
        'NormalCyrillic',
        parent=styles['Normal'],
        fontName=cyrillic_font_name,
        fontSize=10
    )
    
    # Содержимое документа
    story = []
    
    # Заголовок
    title = Paragraph(f'Расписание занятий: {association.name}', title_style)
    story.append(title)
    story.append(Spacer(1, 0.5*cm))
    
    # Период
    period_text = 'Типовая неделя · повторяется каждую неделю'
    story.append(Paragraph(period_text, normal_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Подготовка данных для таблицы
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    
    # Группируем занятия по дням недели
    lessons_by_day = {}
    for lesson in lessons:
        day = lesson.weekday
        if day not in lessons_by_day:
            lessons_by_day[day] = []
        lessons_by_day[day].append(lesson)
    
    # Создаем таблицу
    data = [['День недели', 'Время', 'Аудитория', 'Примечание']]
    
    for day in range(7):
        day_name = weekdays[day]
        if day in lessons_by_day:
            first_lesson = True
            for lesson in lessons_by_day[day]:
                time_str = f"{lesson.start_time.strftime('%H:%M')} - {lesson.end_time.strftime('%H:%M')}"
                classroom = lesson.classroom or '-'
                note = lesson.note or '-'
                
                if first_lesson:
                    data.append([day_name, time_str, classroom, note])
                    first_lesson = False
                else:
                    data.append(['', time_str, classroom, note])
        else:
            data.append([day_name, '-', '-', '-'])
    
    # Создаем таблицу с поддержкой кириллицы
    # Преобразуем данные в Paragraph для правильного отображения кириллицы
    table_data = []
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=normal_style,
        fontName=cyrillic_font_bold_name,
        fontSize=12,
        textColor=colors.whitesmoke,
        alignment=0  # LEFT
    )
    
    for row_idx, row in enumerate(data):
        table_row = []
        for cell in row:
            if isinstance(cell, str) and cell:
                # Для заголовка используем жирный стиль, для остальных - обычный
                if row_idx == 0:
                    table_row.append(Paragraph(cell, header_style))
                else:
                    table_row.append(Paragraph(cell, normal_style))
            else:
                table_row.append(cell)
        table_data.append(table_row)
    
    table = Table(table_data, colWidths=[4*cm, 3*cm, 3*cm, 8*cm])
    
    # Стили таблицы
    table.setStyle(TableStyle([
        # Заголовок
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), cyrillic_font_bold_name),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        # Строки
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(table)
    
    # Генерируем PDF
    doc.build(story)
    
    # Получаем PDF из buffer
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    # Используем безопасное имя файла (без кириллицы в имени)
    safe_name = association.name.replace(' ', '_').replace('/', '_')
    filename = f'Schedule_{safe_name}_{start_of_week.strftime("%Y%m%d")}.pdf'
    # Для кириллицы используем заголовок Content-Disposition с кодировкой
    from urllib.parse import quote
    filename_utf8 = f'Расписание_{association.name}_{start_of_week.strftime("%Y%m%d")}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename_utf8)}'
    
    return response


@login_required
def export_lessons_schedule_excel(request):
    """
    Экспорт расписания занятий в Excel.
    """
    user = request.user
    association_id = request.GET.get('association')
    
    if not association_id:
        messages.error(request, 'Не выбрано объединение')
        return redirect('lessons_schedule')
    
    if user.is_director():
        try:
            association = visible_associations(user).get(id=association_id)
        except (Association.DoesNotExist, ValueError, OverflowError):
            messages.error(request, 'Объединение не найдено')
            return redirect('lessons_schedule')
    else:
        try:
            association = visible_associations(user).get(id=association_id)
        except (Association.DoesNotExist, ValueError, OverflowError):
            messages.error(request, 'Объединение не найдено или у вас нет доступа')
            return redirect('lessons_schedule')
    
    # Получаем занятия для текущей недели
    lessons = Lesson.objects.filter(
        association=association,
        is_template=False
    ).order_by('weekday', 'start_time')
    
    # Определяем текущую неделю
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    # Создаем Excel файл
    wb = Workbook()
    ws = wb.active
    ws.title = 'Расписание занятий'
    
    # Стили
    header_fill = PatternFill(start_color='3b82f6', end_color='3b82f6', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF', size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Заголовок
    ws.merge_cells('A1:D1')
    ws['A1'] = f'Расписание занятий: {association.name}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    
    # Период
    ws.merge_cells('A2:D2')
    ws['A2'] = 'Типовая неделя · повторяется каждую неделю'
    ws['A2'].alignment = Alignment(horizontal='center')
    
    # Заголовки таблицы
    headers = ['День недели', 'Время', 'Аудитория', 'Примечание']
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # Данные
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    lessons_by_day = {}
    for lesson in lessons:
        day = lesson.weekday
        if day not in lessons_by_day:
            lessons_by_day[day] = []
        lessons_by_day[day].append(lesson)
    
    row = 5
    for day in range(7):
        day_name = weekdays[day]
        if day in lessons_by_day:
            first_lesson = True
            for lesson in lessons_by_day[day]:
                time_str = f"{lesson.start_time.strftime('%H:%M')} - {lesson.end_time.strftime('%H:%M')}"
                classroom = lesson.classroom or '-'
                note = lesson.note or '-'
                
                ws.cell(row=row, column=1).value = day_name if first_lesson else ''
                ws.cell(row=row, column=2).value = time_str
                ws.cell(row=row, column=3).value = classroom
                ws.cell(row=row, column=4).value = note
                
                # Применяем стили
                for col in range(1, 5):
                    cell = ws.cell(row=row, column=col)
                    cell.border = border
                    cell.alignment = Alignment(vertical='top', wrap_text=True)
                    if row % 2 == 0:
                        cell.fill = PatternFill(start_color='F5F5F5', end_color='F5F5F5', fill_type='solid')
                
                first_lesson = False
                row += 1
        else:
            ws.cell(row=row, column=1).value = day_name
            ws.cell(row=row, column=2).value = '-'
            ws.cell(row=row, column=3).value = '-'
            ws.cell(row=row, column=4).value = '-'
            
            for col in range(1, 5):
                cell = ws.cell(row=row, column=col)
                cell.border = border
                cell.alignment = Alignment(vertical='top')
            
            row += 1
    
    # Настройка ширины столбцов
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 40
    
    # Сохраняем в BytesIO
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    # Создаем ответ
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    # Используем безопасное имя файла (без кириллицы в имени)
    safe_name = association.name.replace(' ', '_').replace('/', '_')
    filename = f'Schedule_{safe_name}_{start_of_week.strftime("%Y%m%d")}.xlsx'
    # Для кириллицы используем заголовок Content-Disposition с кодировкой
    from urllib.parse import quote
    filename_utf8 = f'Расписание_{association.name}_{start_of_week.strftime("%Y%m%d")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename_utf8)}'
    
    return response


def _get_associations_for_export_all(user):
    """Объединения для экспорта «все КМФ»: директор — все, начальник отдела — своего отдела."""
    if user.is_director():
        return Association.objects.filter(is_active=True).select_related('department').order_by('department__name', 'name')
    if user.is_head():
        return Association.objects.filter(department=user.department, is_active=True).order_by('name')
    return Association.objects.none()


def _register_cyrillic_fonts():
    """Регистрирует шрифты для кириллицы в PDF. Возвращает (font_name, font_bold_name)."""
    cyrillic_font_name = 'DejaVuSans'
    cyrillic_font_bold_name = 'DejaVuSans-Bold'
    if cyrillic_font_name in pdfmetrics.getRegisteredFontNames():
        return cyrillic_font_name, cyrillic_font_bold_name
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
        '/usr/share/fonts/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/TTF/LiberationSans-Regular.ttf',
    ]
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('DejaVuSans', font_path, 'UTF-8'))
                bold_path = font_path.replace('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf')
                if not os.path.exists(bold_path):
                    bold_path = font_path.replace('Regular', 'Bold')
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold_path, 'UTF-8'))
                return cyrillic_font_name, cyrillic_font_bold_name
            except Exception:
                continue
    return 'Helvetica', 'Helvetica-Bold'


@login_required
def export_lessons_schedule_pdf_all(request):
    """
    Экспорт расписания занятий по всем КМФ в один PDF.
    Доступно только директору и начальнику отдела.
    """
    user = request.user
    if not (user.is_director() or user.is_head()):
        messages.error(request, 'Доступ запрещён')
        return redirect('lessons_schedule')

    associations = _get_associations_for_export_all(user)
    if not associations.exists():
        messages.error(request, 'Нет объединений для экспорта')
        return redirect('lessons_schedule')

    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    font_name, font_bold_name = _register_cyrillic_fonts()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=font_bold_name,
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=1,
    )
    normal_style = ParagraphStyle(
        'NormalCyrillic',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
    )
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=normal_style,
        fontName=font_bold_name,
        fontSize=12,
        textColor=colors.whitesmoke,
        alignment=0,
    )
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    for association in associations:
        lessons = Lesson.objects.filter(
            association=association,
            is_template=False,
        ).order_by('weekday', 'start_time')

        story.append(Paragraph(f'Расписание занятий: {association.name}', title_style))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(
            'Типовая неделя · повторяется каждую неделю',
            normal_style,
        ))
        story.append(Spacer(1, 0.5*cm))

        lessons_by_day = {}
        for lesson in lessons:
            d = lesson.weekday
            if d not in lessons_by_day:
                lessons_by_day[d] = []
            lessons_by_day[d].append(lesson)

        data = [['День недели', 'Время', 'Аудитория', 'Примечание']]
        for day in range(7):
            day_name = weekdays[day]
            if day in lessons_by_day:
                first = True
                for lesson in lessons_by_day[day]:
                    time_str = f"{lesson.start_time.strftime('%H:%M')} - {lesson.end_time.strftime('%H:%M')}"
                    classroom = lesson.classroom or '-'
                    note = lesson.note or '-'
                    data.append([day_name if first else '', time_str, classroom, note])
                    first = False
            else:
                data.append([day_name, '-', '-', '-'])

        table_data = []
        for row_idx, row in enumerate(data):
            table_row = []
            for cell in row:
                if isinstance(cell, str) and cell:
                    table_row.append(Paragraph(cell, header_style if row_idx == 0 else normal_style))
                else:
                    table_row.append(cell)
            table_data.append(table_row)

        table = Table(table_data, colWidths=[4*cm, 3*cm, 3*cm, 8*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), font_bold_name),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(table)
        story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    filename = f'Schedule_all_KMF_{start_of_week.strftime("%Y%m%d")}.pdf'
    filename_utf8 = f'Расписание_все_КМФ_{start_of_week.strftime("%Y%m%d")}.pdf'
    from urllib.parse import quote
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename_utf8)}'
    return response


@login_required
def export_lessons_schedule_excel_all(request):
    """
    Экспорт расписания занятий по всем КМФ в один Excel (лист на каждое объединение).
    Доступно только директору и начальнику отдела.
    """
    user = request.user
    if not (user.is_director() or user.is_head()):
        messages.error(request, 'Доступ запрещён')
        return redirect('lessons_schedule')

    associations = _get_associations_for_export_all(user)
    if not associations.exists():
        messages.error(request, 'Нет объединений для экспорта')
        return redirect('lessons_schedule')

    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    wb = Workbook()
    header_fill = PatternFill(start_color='3b82f6', end_color='3b82f6', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF', size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )
    weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

    first_sheet = True
    for association in associations:
        lessons = Lesson.objects.filter(
            association=association,
            is_template=False,
        ).order_by('weekday', 'start_time')

        sheet_name = (association.name[:31]) if len(association.name) > 31 else association.name
        for c in ['\\', '/', '*', '?', ':', '[', ']']:
            sheet_name = sheet_name.replace(c, '_')
        if first_sheet:
            ws = wb.active
            ws.title = sheet_name
            first_sheet = False
        else:
            ws = wb.create_sheet(title=sheet_name)

        ws.merge_cells('A1:D1')
        ws['A1'] = f'Расписание занятий: {association.name}'
        ws['A1'].font = Font(bold=True, size=14)
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.merge_cells('A2:D2')
        ws['A2'] = 'Типовая неделя · повторяется каждую неделю'
        ws['A2'].alignment = Alignment(horizontal='center')

        for col_num, header in enumerate(['День недели', 'Время', 'Аудитория', 'Примечание'], 1):
            cell = ws.cell(row=4, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border

        lessons_by_day = {}
        for lesson in lessons:
            d = lesson.weekday
            if d not in lessons_by_day:
                lessons_by_day[d] = []
            lessons_by_day[d].append(lesson)

        row = 5
        for day in range(7):
            day_name = weekdays[day]
            if day in lessons_by_day:
                first_lesson = True
                for lesson in lessons_by_day[day]:
                    time_str = f"{lesson.start_time.strftime('%H:%M')} - {lesson.end_time.strftime('%H:%M')}"
                    classroom = lesson.classroom or '-'
                    note = lesson.note or '-'
                    ws.cell(row=row, column=1).value = day_name if first_lesson else ''
                    ws.cell(row=row, column=2).value = time_str
                    ws.cell(row=row, column=3).value = classroom
                    ws.cell(row=row, column=4).value = note
                    for col in range(1, 5):
                        c = ws.cell(row=row, column=col)
                        c.border = border
                        c.alignment = Alignment(vertical='top', wrap_text=True)
                        if row % 2 == 0:
                            c.fill = PatternFill(start_color='F5F5F5', end_color='F5F5F5', fill_type='solid')
                    first_lesson = False
                    row += 1
            else:
                ws.cell(row=row, column=1).value = day_name
                ws.cell(row=row, column=2).value = '-'
                ws.cell(row=row, column=3).value = '-'
                ws.cell(row=row, column=4).value = '-'
                for col in range(1, 5):
                    c = ws.cell(row=row, column=col)
                    c.border = border
                    c.alignment = Alignment(vertical='top')
                row += 1

        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 40

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    filename = f'Schedule_all_KMF_{start_of_week.strftime("%Y%m%d")}.xlsx'
    filename_utf8 = f'Расписание_все_КМФ_{start_of_week.strftime("%Y%m%d")}.xlsx'
    from urllib.parse import quote
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename_utf8)}'
    return response

