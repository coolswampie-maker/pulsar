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


@admin.register(BusySlot)
class BusySlotAdmin(admin.ModelAdmin):
    date_hierarchy = 'date'                      # навигация по годам/месяцам/дням
    list_display = ('date', 'slot_start', 'slot_end', 'resource', 'note')
    list_filter = ('date', 'resource__type', 'resource')
    search_fields = ('resource__title', 'note')
    autocomplete_fields = ('resource',)
    ordering = ('date', 'slot_start')
