"""
Модели ПУЛЬСАР. Зеркалят структуру фронтенда (data/resources.js) +
заявки/брони. Персональные данные заявок хранятся в РФ (152-ФЗ).
"""
from datetime import time

from django.conf import settings
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


class Company(models.Model):
    """Компания-резидент кластера «Ломоносов» — владелец личного кабинета."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='company', verbose_name='Учётная запись')
    name = models.CharField('Организация', max_length=200)
    inn = models.CharField('ИНН', max_length=12, blank=True)
    category = models.CharField('Направление', max_length=12, choices=CATEGORIES, blank=True)
    resident = models.BooleanField('Резидент ИНТЦ', default=False)
    confirmed = models.BooleanField('Подтверждена оператором', default=False)
    contact_name = models.CharField('Контактное лицо', max_length=200, blank=True)
    phone = models.CharField('Телефон', max_length=40, blank=True)
    created_at = models.DateTimeField('Зарегистрирована', auto_now_add=True)

    class Meta:
        verbose_name = 'Компания'
        verbose_name_plural = 'Компании'
        ordering = ['name']

    def __str__(self):
        return self.name


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
    work_start = models.TimeField('Работает с', default=time(8, 0))
    work_end = models.TimeField('Работает до', default=time(20, 0))

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
    """Заявка на бронирование. Может быть от компании из ЛК или гостевая/операторская."""
    number = models.CharField('Номер', max_length=20, unique=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    status = models.CharField('Статус', max_length=12, choices=ORDER_STATUS, default='new')

    company = models.ForeignKey('Company', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='orders', verbose_name='Компания')
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
        from django.utils import timezone
        errors = {}
        # Нельзя забронировать больше единиц, чем есть в наличии.
        if self.resource_id and self.qty and self.qty > self.resource.units_total:
            errors['qty'] = f'Больше, чем есть в наличии ({self.resource.units_total}).'
        # Окончание должно быть позже начала.
        if self.slot_start and self.slot_end and self.slot_end <= self.slot_start:
            errors['slot_end'] = 'Окончание должно быть позже начала.'
        # В пределах рабочих часов ресурса.
        if self.resource_id and self.slot_start and self.slot_end:
            ws, we = self.resource.work_start, self.resource.work_end
            if (ws and self.slot_start < ws) or (we and self.slot_end > we):
                errors['slot_start'] = f'Вне рабочих часов ресурса ({ws:%H:%M}–{we:%H:%M}).'
        # Новую позицию нельзя ставить в прошлое (историю править можно).
        if self.date and self._state.adding and self.date < timezone.localdate():
            errors['date'] = 'Дата в прошлом.'
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


# 6 ключевых показателей по Методологии оценки деятельности участников ИНТЦ.
# (key, наименование, единица, норма-подсказка, требуемые подтверждающие документы)
KPI_DEFS = [
    ('rid',     'Количество РИД',              'шт',        '',
     'Копии патентов и заявок на регистрацию (изобретение, ПО, БД), оформленные ноу-хау; основание права.'),
    ('rnd',     'Инвестиции в НИОКР',          '% выручки', 'норма ≥ 10%',
     'Бухбаланс (стр. 1120), отчёт о фин. результатах, форма П-2 (инвест); при 5–10% — обоснование.'),
    ('infra',   'Инвестиции в инфраструктуру', '% выручки', 'норма ≥ 1%',
     'Договоры и документы, подтверждающие инвестиции в инфраструктуру ИНТЦ.'),
    ('staff',   'Численность работников',      'чел',       '',
     'Документы по штату из календарного плана (трудовые договоры, штатное расписание).'),
    ('revenue', 'Выручка',                     '₽',         '',
     'Договоры продаж и бухотчётность; форма по ОКУД 0710002; оборотно-сальдовая по счёту 90.'),
    ('export',  'Доля экспорта',               '%',         '',
     'Экспортные договоры и бухотчётность (продажи за рубеж без обязательства обратного ввоза).'),
]
KPI_KEYS = [d[0] for d in KPI_DEFS]
KPI_META = {d[0]: {'label': d[1], 'unit': d[2], 'hint': d[3], 'docs': d[4]} for d in KPI_DEFS}


class Kpi(models.Model):
    """Ключевой показатель компании за год: план (оператор) + факт (компания)."""
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='kpis', verbose_name='Компания')
    year = models.PositiveSmallIntegerField('Год')
    key = models.CharField('Показатель', max_length=12, choices=[(d[0], d[1]) for d in KPI_DEFS])
    plan = models.DecimalField('План', max_digits=16, decimal_places=2, null=True, blank=True)
    fact = models.DecimalField('Факт', max_digits=16, decimal_places=2, null=True, blank=True)
    document = models.FileField('Подтверждающий документ', upload_to='kpi_docs/', null=True, blank=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Показатель'
        verbose_name_plural = 'Показатели'
        unique_together = ('company', 'year', 'key')
        ordering = ['company', '-year']

    def __str__(self):
        return f'{self.company_id} · {self.year} · {self.get_key_display()}'

    # Показатели-доли считаются в % от выручки (нормы методологии заданы в %).
    PERCENT_KEYS = ('rnd', 'infra', 'export')

    def recompute(self):
        """Факт = сумма позиций (что компания завела в ЛК)."""
        from django.db.models import Sum
        self.fact = self.entries.aggregate(s=Sum('amount'))['s']
        self.save(update_fields=['fact', 'updated_at'])

    @property
    def value(self):
        """Сравнимое с планом значение: для долей — процент от выручки, иначе — факт."""
        if self.fact is None:
            return None
        if self.key in self.PERCENT_KEYS:
            rev = (Kpi.objects.filter(company_id=self.company_id, year=self.year, key='revenue')
                   .values_list('fact', flat=True).first())
            if not rev:
                return None
            return round(float(self.fact) / float(rev) * 100, 2)
        return float(self.fact)

    @property
    def status(self):
        """ok — достигнут; warn — ниже плана, но в пределах 20%; bad — существенное
        недовыполнение (>20%); none — нет данных. По п.3.5 Методологии."""
        val = self.value
        if self.plan in (None, 0) or val is None:
            return 'none'
        ratio = float(val) / float(self.plan)
        if ratio >= 1:
            return 'ok'
        if ratio >= 0.8:
            return 'warn'
        return 'bad'


class KpiEntry(models.Model):
    """Позиция показателя: что сделано / на что потрачено. Факт показателя = их сумма."""
    SOURCES = [('manual', 'Вручную'), ('auto', 'Из документа')]
    kpi = models.ForeignKey(Kpi, on_delete=models.CASCADE, related_name='entries', verbose_name='Показатель')
    title = models.CharField('Наименование', max_length=300)
    amount = models.DecimalField('Сумма / количество', max_digits=16, decimal_places=2, null=True, blank=True)
    date = models.DateField('Дата', null=True, blank=True)
    document = models.FileField('Документ', upload_to='kpi_docs/', null=True, blank=True)
    source = models.CharField('Источник', max_length=8, choices=SOURCES, default='manual')
    created_at = models.DateTimeField('Добавлена', auto_now_add=True)

    class Meta:
        verbose_name = 'Позиция показателя'
        verbose_name_plural = 'Позиции показателей'
        ordering = ['-date', '-id']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.kpi.recompute()

    def delete(self, *args, **kwargs):
        kpi = self.kpi
        super().delete(*args, **kwargs)
        kpi.recompute()
