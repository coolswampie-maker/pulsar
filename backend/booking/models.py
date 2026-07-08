"""
Модели ПУЛЬСАР. Зеркалят структуру фронтенда (data/resources.js) +
заявки/брони. Персональные данные заявок хранятся в РФ (152-ФЗ).
"""
from django.db import models

RES_TYPES = [
    ('room', 'Лаборатория'),
    ('equipment', 'Оборудование'),
    ('specialist', 'Специалист'),
    ('service', 'Услуга под ключ'),
]
BOOK_MODES = [
    ('shift', 'Смена (8 ч)'),
    ('day', 'Сутки'),
    ('hour', 'Час'),
    ('sample', 'Образец'),
]
CATEGORIES = [
    ('bio', 'Биотехнологии'), ('pharma', 'Фармацевтика'), ('micro', 'Микроэлектроника'),
    ('vacuum', 'Вакуум и испытания'), ('genetics', 'Молекулярная генетика'),
    ('materials', 'Новые материалы'), ('food', 'Функциональное питание'), ('analytics', 'Аналитика'),
]
ORDER_STATUS = [('new', 'Новая'), ('confirmed', 'Подтверждена'), ('rejected', 'Отклонена')]


class Resource(models.Model):
    """Единая карточка ресурса: лаборатория / прибор / специалист / услуга."""
    slug = models.SlugField('Идентификатор', primary_key=True, max_length=60)
    type = models.CharField('Тип', max_length=12, choices=RES_TYPES)
    category = models.CharField('Направление', max_length=12, choices=CATEGORIES, blank=True)
    book_mode = models.CharField('Единица брони', max_length=8, choices=BOOK_MODES)

    title = models.CharField('Наименование', max_length=200)
    lab = models.CharField('Подразделение / лаборатория', max_length=160, blank=True)
    clean_class = models.CharField('Класс чистоты / статус', max_length=60, blank=True)
    description = models.TextField('Описание', blank=True)
    specs = models.JSONField('Характеристики (список)', default=list, blank=True)

    price_value = models.PositiveIntegerField('Цена, ₽', default=0)
    price_unit = models.CharField('Единица цены', max_length=20, default='час')
    min_units = models.PositiveSmallIntegerField('Мин. единиц', default=1)
    units_total = models.PositiveSmallIntegerField(
        'Единиц в наличии', default=1,
        help_text='Сколько одинаковых единиц ресурса есть физически (приборов, мест, специалистов).')

    image = models.CharField('Ключ/URL фото', max_length=200, blank=True)
    requires_operator = models.ForeignKey(
        'self', verbose_name='Требует оператора', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='operates')
    bundled_with = models.ManyToManyField(
        'self', verbose_name='Входит в комплект', blank=True, symmetrical=False)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Ресурс'
        verbose_name_plural = 'Каталог ресурсов'
        ordering = ['type', 'title']

    def __str__(self):
        return f'{self.get_type_display()}: {self.title}'


class BusySlot(models.Model):
    """Общий календарь занятости (единый для всех). Автозаполняется при подтверждении заявки."""
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='busy', verbose_name='Ресурс')
    date = models.DateField('Дата')
    slot_start = models.TimeField('Начало', null=True, blank=True)
    slot_end = models.TimeField('Окончание', null=True, blank=True)
    note = models.CharField('Пометка', max_length=120, blank=True)

    class Meta:
        verbose_name = 'Занятость'
        verbose_name_plural = 'Календарь занятости'
        ordering = ['date', 'slot_start']

    def __str__(self):
        return f'{self.resource_id} · {self.date} {self.slot_start or ""}'


class Order(models.Model):
    """Заявка на бронирование (гостевая). Мини-CRM оператора."""
    number = models.CharField('Номер', max_length=20, unique=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    status = models.CharField('Статус', max_length=12, choices=ORDER_STATUS, default='new')

    org = models.CharField('Организация', max_length=200)
    contact_name = models.CharField('Контактное лицо', max_length=200, blank=True)
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Телефон', max_length=40, blank=True)
    note = models.TextField('Комментарий', blank=True)
    resident = models.BooleanField('Резидент ИНТЦ', default=False)

    subtotal = models.PositiveIntegerField('Стоимость, ₽', default=0)
    discount = models.PositiveIntegerField('Скидка, ₽', default=0)
    total = models.PositiveIntegerField('Итого, ₽', default=0)

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.number} — {self.org} ({self.get_status_display()})'

    def sync_busy_slots(self):
        """Пересобирает слоты календаря по текущим позициям заявки.
        Сначала убираем все слоты этой заявки (чтобы не оставалось «призраков»
        после переноса/удаления позиций), затем для подтверждённой создаём заново."""
        tag = f'Заявка {self.number}'
        BusySlot.objects.filter(note=tag).delete()
        if self.status == 'confirmed':
            for line in self.lines.all():
                if line.date:
                    BusySlot.objects.create(
                        resource=line.resource, date=line.date,
                        slot_start=line.slot_start, slot_end=line.slot_end, note=tag)

    @staticmethod
    def next_number():
        import re
        mx = 1000
        for n in Order.objects.values_list('number', flat=True):
            m = re.match(r'PLS-(\d+)$', n or '')
            if m:
                mx = max(mx, int(m.group(1)))
        return f'PLS-{mx + 1}'

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.next_number()
        old_status = None
        if self.pk:
            old_status = type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()
        super().save(*args, **kwargs)
        if self.status != old_status:
            self.sync_busy_slots()


class BookingLine(models.Model):
    """Позиция заявки: ресурс + дата/слот. Оператор к прибору — связанная строка."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='lines', verbose_name='Заявка')
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, verbose_name='Ресурс')
    date = models.DateField('Дата', null=True, blank=True)
    slot_start = models.TimeField('Начало', null=True, blank=True)
    slot_end = models.TimeField('Окончание', null=True, blank=True)
    qty = models.PositiveSmallIntegerField('Кол-во', default=1)
    hours = models.PositiveSmallIntegerField('Часы', null=True, blank=True)
    unit_price = models.PositiveIntegerField('Цена/ед.', default=0)
    line_price = models.PositiveIntegerField('Сумма строки', default=0)
    is_operator = models.BooleanField('Оператор к прибору', default=False)
    linked_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='linked')

    class Meta:
        verbose_name = 'Позиция заявки'
        verbose_name_plural = 'Позиции заявки'

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        # Нельзя забронировать больше единиц, чем есть в наличии.
        if self.resource_id and self.qty and self.qty > self.resource.units_total:
            errors['qty'] = f'Больше, чем есть в наличии ({self.resource.units_total}).'
        # Окончание должно быть позже начала.
        if self.slot_start and self.slot_end and self.slot_end <= self.slot_start:
            errors['slot_end'] = 'Окончание должно быть позже начала.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Сумма строки считается автоматически: цена × (часы для почасовых) × кол-во.
        if self.resource_id:
            self.unit_price = self.resource.price_value
            per = self.hours if (self.resource.book_mode == 'hour' and self.hours) else 1
            self.line_price = self.unit_price * per * (self.qty or 1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.resource_id} · {self.date or "—"}'
