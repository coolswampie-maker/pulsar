"""
Админка = back-office оператора:
 • Каталог ресурсов — карточка ввода/редактирования оборудования и лабораторий.
 • Заявки — мини-CRM: статусы, состав, контакты, массовые действия.
 • Календарь занятости.
"""
from django.contrib import admin

from .models import BookingLine, BusySlot, Order, Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'category', 'price_value', 'price_unit', 'is_active')
    list_filter = ('type', 'category', 'is_active')
    search_fields = ('slug', 'title', 'lab')
    list_editable = ('is_active',)
    filter_horizontal = ('bundled_with',)
    fieldsets = (
        (None, {'fields': ('slug', 'type', 'category', 'book_mode', 'is_active')}),
        ('Карточка', {'fields': ('title', 'lab', 'clean_class', 'description', 'specs', 'image')}),
        ('Цена', {'fields': ('price_value', 'price_unit', 'min_units')}),
        ('Связи', {'fields': ('requires_operator', 'bundled_with')}),
    )


class BookingLineInline(admin.TabularInline):
    model = BookingLine
    extra = 0
    fields = ('resource', 'date', 'slot_start', 'slot_end', 'qty', 'hours', 'line_price', 'is_operator')
    autocomplete_fields = ('resource',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'org', 'contact_name', 'status', 'total', 'created_at')
    list_filter = ('status', 'resident', 'created_at')
    search_fields = ('number', 'org', 'contact_name', 'email', 'phone')
    readonly_fields = ('number', 'created_at', 'subtotal', 'discount', 'total')
    inlines = [BookingLineInline]
    actions = ['mark_confirmed', 'mark_rejected']

    def save_related(self, request, form, formsets, change):
        # позиции сохраняются после заявки — синхронизируем календарь уже с ними
        super().save_related(request, form, formsets, change)
        form.instance.sync_busy_slots()

    @admin.action(description='Подтвердить выбранные заявки')
    def mark_confirmed(self, request, queryset):
        for order in queryset:
            order.status = 'confirmed'
            order.save()  # save() сам заносит слоты в календарь
        self.message_user(request, f'Подтверждено заявок: {queryset.count()}')

    @admin.action(description='Отклонить выбранные заявки')
    def mark_rejected(self, request, queryset):
        for order in queryset:
            order.status = 'rejected'
            order.save()  # save() уберёт слоты этой заявки из календаря


GANTT_CSS = """
body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;margin:0;background:#f5f6f8;color:#1b2733}
.top{background:#264b63;color:#fff;padding:9px 16px;font-size:13px}
.top a{color:#cfe0f0;text-decoration:none;margin-right:8px}
.top a:hover{color:#fff}
h1{font-size:19px;margin:18px 16px 4px}
.sub{margin:0 16px 14px;color:#889;font-size:13px}
.wrap{overflow-x:auto;margin:0 16px 14px;border:1px solid #dde;border-radius:8px;background:#fff}
table{border-collapse:collapse;min-width:900px;font-size:12px;width:100%}
th,td{border:1px solid #eef}
th{background:#f0f3f7;position:sticky;top:0;text-align:center;padding:6px 4px;font-weight:600;min-width:118px}
th b{display:block}
th span{color:#8892a0;font-weight:400;font-size:11px}
th.wknd,td.wknd{background:#faf6f0}
.rescol{position:sticky;left:0;background:#fff;z-index:2;text-align:left;padding:9px 11px;min-width:240px;max-width:240px;border-right:2px solid #dde;font-weight:600;line-height:1.3}
th.rescol{z-index:3;background:#f0f3f7}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px;vertical-align:middle}
td.day{position:relative;height:34px;padding:0;background-image:repeating-linear-gradient(90deg,transparent 0,transparent calc(8.333% - 1px),#e9edf3 calc(8.333% - 1px),#e9edf3 8.333%)}
td.day.wknd{background-color:#faf6f0}
.bar{position:absolute;top:4px;bottom:4px;border-radius:4px;color:#fff;font-size:10px;display:flex;align-items:center;justify-content:center;overflow:hidden;white-space:nowrap;padding:0 3px;box-shadow:0 1px 2px rgba(0,0,0,.18);font-variant-numeric:tabular-nums}
.today{box-shadow:inset 0 3px 0 #c99b3f}
.empty{padding:30px;text-align:center;color:#889}
.legend{margin:0 16px 26px;font-size:12px;color:#556;display:flex;gap:18px;flex-wrap:wrap}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:middle}
"""
GANTT_COLORS = {'room': '#2e5b8a', 'equipment': '#8a5a2e', 'specialist': '#5a2e8a', 'service': '#2e8a6a'}
GANTT_LABELS = {'room': 'Лаборатории', 'equipment': 'Оборудование', 'specialist': 'Специалисты', 'service': 'Услуги'}
WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']


@admin.register(BusySlot)
class BusySlotAdmin(admin.ModelAdmin):
    date_hierarchy = 'date'                      # навигация по годам/месяцам/дням
    list_display = ('date', 'slot_start', 'slot_end', 'resource', 'note')
    list_filter = ('date', 'resource__type', 'resource')
    search_fields = ('resource__title', 'note')
    autocomplete_fields = ('resource',)
    ordering = ('date', 'slot_start')
    change_list_template = 'admin/booking/busyslot/change_list.html'

    def get_urls(self):
        from django.urls import path
        extra = [path('gantt/', self.admin_site.admin_view(self.gantt_view),
                      name='booking_busyslot_gantt')]
        return extra + super().get_urls()

    def gantt_view(self, request):
        """Общее расписание в стиле Ганта: ресурсы × дни, брони — полосами."""
        from collections import OrderedDict
        from datetime import timedelta
        from django.http import HttpResponse
        from django.utils import timezone
        from django.utils.html import escape

        try:
            span = max(7, min(60, int(request.GET.get('days', 14))))
        except ValueError:
            span = 14
        today = timezone.localdate()
        days = [today + timedelta(days=i) for i in range(span)]

        slots = (BusySlot.objects.select_related('resource')
                 .filter(date__gte=days[0], date__lte=days[-1])
                 .order_by('resource__type', 'resource__title', 'date', 'slot_start'))

        resources = OrderedDict()
        cells = {}
        for s in slots:
            resources.setdefault(s.resource_id, s.resource)
            cells.setdefault((s.resource_id, s.date), []).append(s)

        DAY_START, DAY_END = 8.0, 20.0            # рабочее окно на шкале дня
        SPAN_H = DAY_END - DAY_START

        def daycls(d):
            c = 'wknd' if d.weekday() >= 5 else ''
            if d == today:
                c = (c + ' today').strip()
            return c

        def bar_html(slot, color):
            if slot.slot_start:
                s = slot.slot_start.hour + slot.slot_start.minute / 60
                e = (slot.slot_end.hour + slot.slot_end.minute / 60) if slot.slot_end else s + 1
                s = max(DAY_START, min(DAY_END, s)); e = max(DAY_START, min(DAY_END, e))
                if e <= s:
                    e = s + 0.5
                left = (s - DAY_START) / SPAN_H * 100
                width = max(7, (e - s) / SPAN_H * 100)
                short = slot.slot_start.strftime('%H:%M')
                full = slot.slot_start.strftime('%H:%M') + '–' + (slot.slot_end.strftime('%H:%M') if slot.slot_end else '')
                style = f'left:{left:.1f}%;width:{width:.1f}%;background:{color}'
            else:
                short, full = 'весь день', 'весь день'
                style = f'left:1%;width:98%;background:{color}'
            title = full + (' · ' + slot.note if slot.note else '')
            return f'<div class="bar" style="{style}" title="{escape(title)}">{escape(short)}</div>'

        head = '<th class="rescol">Ресурс</th>' + ''.join(
            f'<th class="{daycls(d)}"><b>{d.day:02d}.{d.month:02d}</b>'
            f'<span>{WEEKDAYS[d.weekday()]}</span></th>' for d in days)

        rows = ''
        for pk, r in resources.items():
            color = GANTT_COLORS.get(r.type, '#555')
            tds = ''
            for d in days:
                items = cells.get((pk, d)) or []
                inner = ''.join(bar_html(s, color) for s in items)
                tds += f'<td class="day {daycls(d)}">{inner}</td>'
            rows += (f'<tr><td class="rescol"><span class="dot" style="background:{color}"></span>'
                     f'{escape(r.title)}</td>{tds}</tr>')

        if not resources:
            rows = (f'<tr><td colspan="{span + 1}" class="empty">Нет подтверждённых броней на этот период. '
                    f'Подтвердите заявку — её позиции появятся здесь.</td></tr>')

        legend = ''.join(f'<span><i style="background:{GANTT_COLORS[t]}"></i>{GANTT_LABELS[t]}</span>'
                         for t in GANTT_COLORS)

        html = (
            '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">'
            '<title>Расписание · ПУЛЬСАР</title><style>' + GANTT_CSS + '</style></head><body>'
            '<div class="top"><a href="../">← к списку занятости</a>'
            '<a href="/admin/">админка</a>'
            '<a href="?days=7">7 дней</a><a href="?days=14">14 дней</a><a href="?days=30">30 дней</a></div>'
            '<h1>Общее расписание · Гант</h1>'
            f'<div class="sub">Подтверждённые брони на {span} дней · шкала дня 8:00–20:00 (деления по часам). '
            'Полосы позиционируются по времени — свободные промежутки видны, день набивается плотно.</div>'
            '<div class="wrap"><table><thead><tr>' + head + '</tr></thead><tbody>' + rows +
            '</tbody></table></div>'
            '<div class="legend">' + legend + '</div>'
            '</body></html>')
        return HttpResponse(html)
