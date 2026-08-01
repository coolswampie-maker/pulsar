"""
Модели ПУЛЬСАР. Зеркалят структуру фронтенда (data/resources.js) +
заявки/брони. Персональные данные заявок хранятся в РФ (152-ФЗ).
"""
from datetime import time

from django.conf import settings
from django.db import models
from django.utils import timezone

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
# --- проверка загружаемых документов ---
# Живёт в модели, а не в сериализаторе: проверка в API не защищает кабинет
# оператора, где файл кладут через админку в обход сериализатора. Правило
# должно быть одно на все пути записи.
#
# Зачем вообще: без разбора расширений на сайт можно положить .html, и он
# отдаётся с нашего домена как обычная страница — это готовый XSS. Nginx
# отдаёт /media/ вложением и с nosniff, но полагаться на одну преграду там,
# где файл загружает посторонний, не стоит.
DOC_EXTS = ('pdf', 'jpg', 'jpeg', 'png', 'webp', 'heic',
            'doc', 'docx', 'xls', 'xlsx', 'odt', 'ods', 'rtf', 'txt', 'zip', 'rar', '7z')
DOC_MAX_MB = 25


def validate_doc_file(f):
    """Расширение из белого списка и размер не больше DOC_MAX_MB."""
    import os

    from django.core.exceptions import ValidationError
    name = getattr(f, 'name', '') or ''
    ext = os.path.splitext(name)[1].lower().lstrip('.')
    if ext not in DOC_EXTS:
        raise ValidationError(
            'Недопустимый формат файла «.%(ext)s». Разрешены: %(ok)s.',
            params={'ext': ext or '?', 'ok': ', '.join(DOC_EXTS)})
    size = getattr(f, 'size', 0) or 0
    if size > DOC_MAX_MB * 1024 * 1024:
        raise ValidationError('Файл больше %(mb)s МБ.', params={'mb': DOC_MAX_MB})


ORDER_STATUS = [('new', 'Новая'), ('confirmed', 'Подтверждена'), ('rejected', 'Отклонена')]
CUSTOM_STATUS = [('new', 'Новая'), ('in_work', 'В работе'),
                 ('done', 'Обработана'), ('rejected', 'Отклонена')]


# Версия согласия на обработку персональных данных. Поднимается при каждом
# существенном изменении политики. Хранить именно версию, а не просто «да»:
# иначе через год нельзя будет ответить, на какую редакцию человек соглашался.
CONSENT_VERSION = '2026-08-01'


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

    # --- реквизиты: нужны только для проверки на формальные отказы ---
    # Спрашиваем не при регистрации, а когда доходит до проверки: программы
    # отсекают заявителей именно по этим полям.
    ogrn = models.CharField('ОГРН', max_length=15, blank=True)
    okved = models.CharField('ОКВЭД', max_length=200, blank=True,
                             help_text='Основной и дополнительные, через запятую.')
    founded = models.DateField('Дата регистрации', null=True, blank=True)
    staff = models.PositiveIntegerField('Численность', null=True, blank=True)
    revenue = models.BigIntegerField('Выручка за прошлый год, ₽', null=True, blank=True)

    # --- согласие на обработку персональных данных ---
    consent_at = models.DateTimeField('Согласие на обработку ПДн', null=True, blank=True)
    consent_version = models.CharField('Редакция политики', max_length=20, blank=True)

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
    change_request = models.TextField('Запрос на изменение (от компании)', blank=True)
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
        # Нельзя забронировать больше единиц, чем есть в наличии. У услуг «под ключ»
        # qty — это количество образцов в партии, а не одновременно занятые единицы,
        # поэтому наличием оно не ограничивается.
        if (self.resource_id and self.qty and self.resource.book_mode != 'sample'
                and self.qty > self.resource.units_total):
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


class CustomRequest(models.Model):
    """Индивидуальная заявка на подбор.

    Появляется, когда клиент не нашёл нужного в каталоге: вместо того чтобы
    уйти, он описывает своими словами, что требуется. Для оператора это
    одновременно и лид, и сигнал, чего в каталоге не хватает.
    """
    number = models.CharField('Номер', max_length=20, unique=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    status = models.CharField('Статус', max_length=12, choices=CUSTOM_STATUS, default='new')

    company = models.ForeignKey('Company', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='custom_requests', verbose_name='Компания')
    org = models.CharField('Организация', max_length=200, blank=True)
    contact_name = models.CharField('Контактное лицо', max_length=200, blank=True)
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Телефон', max_length=40, blank=True)

    need = models.TextField('Что требуется')
    period = models.CharField('Желаемые сроки', max_length=200, blank=True,
                              help_text='Заполняется по желанию клиента.')
    # с каким запросом человек ничего не нашёл — подсказывает, чего не хватает в каталоге
    search_query = models.CharField('Что искали', max_length=300, blank=True)
    operator_note = models.TextField('Комментарий оператора', blank=True)

    class Meta:
        verbose_name = 'Индивидуальная заявка'
        verbose_name_plural = 'Индивидуальные заявки'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.number} — {self.org or self.contact_name or "без организации"}'

    @staticmethod
    def next_number():
        import re
        mx = 1000
        for n in CustomRequest.objects.values_list('number', flat=True):
            m = re.match(r'IND-(\d+)$', n or '')
            if m:
                mx = max(mx, int(m.group(1)))
        return f'IND-{mx + 1}'

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.next_number()
        super().save(*args, **kwargs)


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
    document = models.FileField('Подтверждающий документ', upload_to='kpi_docs/',
                                null=True, blank=True, validators=[validate_doc_file])
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
    document = models.FileField('Документ', upload_to='kpi_docs/',
                                null=True, blank=True, validators=[validate_doc_file])
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


# ============================================================ ПРОФИЛЬ ПРОЕКТА
# Резидент рассказывает о проекте один раз, дальше система раскладывает этот
# рассказ по чужим формам: черновики разделов заявки, тизер, презентация.
# Смысл всей затеи в том, чтобы не заполнять пятую анкету заново.
#
# Поля намеренно текстовые и необязательные: профиль заполняется по частям, а
# незаполненное — это не ошибка, а повод спросить в нужный момент.

PROFILE_STAGES = [
    ('idea', 'Идея'),
    ('calc', 'Расчёты и моделирование'),
    ('lab', 'Лабораторный образец'),
    ('proto', 'Опытный образец'),
    ('test', 'Испытания'),
    ('serial', 'Серийное производство'),
]

# ЕДИНСТВЕННЫЙ источник правды по полям профиля: ключ, подпись, вопрос
# интервью, вид поля, раздел. Всё остальное — списки, словари, состав
# сериализатора и описание полей для браузера — выводится отсюда.
#
# Так сделано не для красоты. Раньше этот список был расписан в семи местах,
# и четыре расхождения не давали никакой ошибки. Худшее: забыть поле в
# составе сериализатора — тогда сервер молча выбрасывает присланное значение,
# интервью снова спрашивает то же самое, и человек ходит по кругу без единого
# сообщения об ошибке. Тот же приём уже применён рядом для показателей
# (KPI_DEFS), это просто возврат к принятому здесь порядку.
#
# вид: line — короткая строка, text — многострочное поле, choice — выбор.
PROFILE_DEFS = [
    ('title', 'Название проекта', 'Как называется ваш проект или разработка?',
     'line', 'core'),
    ('summary', 'Суть в двух фразах',
     'Опишите в двух фразах: что вы делаете и для кого?', 'text', 'core'),
    ('problem', 'Какую задачу решаете',
     'Какую задачу это решает? Чья это боль и почему она важна?', 'text', 'core'),
    ('solution', 'Как решаете и в чём новизна',
     'Как именно вы её решаете? В чём отличие от существующих способов?',
     'text', 'core'),
    ('stage', 'Стадия готовности',
     'На какой стадии проект: идея, расчёты, лабораторный образец, '
     'опытный образец, испытания или уже серия?', 'choice', 'core'),
    ('groundwork', 'Научный задел',
     'Что уже есть: публикации, патенты, диссертации, прототипы, '
     'результаты испытаний?', 'text', 'core'),
    ('team', 'Команда',
     'Кто в команде? Роль и компетенция каждого — трёх-шести человек достаточно.',
     'text', 'core'),
    ('market', 'Рынок и его объём',
     'Кто ваши покупатели и насколько велик рынок? Если есть оценка — с источником.',
     'text', 'extra'),
    ('competitors', 'Конкуренты и отличия',
     'Кто ещё решает эту задачу и чем вы лучше?', 'text', 'extra'),
    ('business_model', 'Как проект зарабатывает',
     'Как проект будет зарабатывать?', 'text', 'extra'),
    ('workplan', 'План работ по этапам',
     'Какие этапы работ планируете и в какие сроки?', 'text', 'extra'),
    ('risks', 'Риски',
     'Что может пойти не так и как вы это предусмотрели?', 'text', 'extra'),
    ('needs', 'Какое оборудование и методы нужны',
     'Какое оборудование, методы или лаборатории нужны для работ?',
     'text', 'extra'),
]

PROFILE_KEYS = [d[0] for d in PROFILE_DEFS]
PROFILE_CORE = [d[0] for d in PROFILE_DEFS if d[4] == 'core']
PROFILE_EXTRA = [d[0] for d in PROFILE_DEFS if d[4] == 'extra']
PROFILE_LABELS = {d[0]: d[1] for d in PROFILE_DEFS}
PROFILE_QUESTIONS = {d[0]: d[2] for d in PROFILE_DEFS}
PROFILE_KINDS = {d[0]: d[3] for d in PROFILE_DEFS}


def profile_field_spec():
    """Описание полей для браузера: подписи и виды приходят с сервера.

    Иначе список полей пришлось бы держать ещё и в JS — а разошедшийся
    список стадий молча стирает выбранную стадию при сохранении формы.
    """
    return [{'key': k, 'label': PROFILE_LABELS[k], 'kind': PROFILE_KINDS[k],
             'options': ([{'value': v, 'label': t} for v, t in PROFILE_STAGES]
                         if PROFILE_KINDS[k] == 'choice' else None)}
            for k in PROFILE_KEYS]


class ProjectProfile(models.Model):
    """Единый рассказ резидента о проекте.

    Одна компания — один профиль. Если проектов станет несколько, добавится
    внешний ключ и выбор; пока это усложнило бы интерфейс без пользы.
    """
    company = models.OneToOneField('Company', on_delete=models.CASCADE,
                                   related_name='profile', verbose_name='Компания')
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    title = models.CharField(PROFILE_LABELS['title'], max_length=250, blank=True)
    summary = models.TextField(PROFILE_LABELS['summary'], blank=True)
    problem = models.TextField(PROFILE_LABELS['problem'], blank=True)
    solution = models.TextField(PROFILE_LABELS['solution'], blank=True)
    stage = models.CharField(PROFILE_LABELS['stage'], max_length=12,
                             choices=PROFILE_STAGES, blank=True)
    groundwork = models.TextField(PROFILE_LABELS['groundwork'], blank=True)
    team = models.TextField(PROFILE_LABELS['team'], blank=True)

    market = models.TextField(PROFILE_LABELS['market'], blank=True)
    competitors = models.TextField(PROFILE_LABELS['competitors'], blank=True)
    business_model = models.TextField(PROFILE_LABELS['business_model'], blank=True)
    workplan = models.TextField(PROFILE_LABELS['workplan'], blank=True)
    risks = models.TextField(PROFILE_LABELS['risks'], blank=True)
    needs = models.TextField(PROFILE_LABELS['needs'], blank=True)

    class Meta:
        verbose_name = 'Профиль проекта'
        verbose_name_plural = 'Профили проектов'

    def __str__(self):
        return self.title or f'Профиль {self.company.name}'

    def missing(self, keys):
        return [k for k in keys if not (getattr(self, k) or '').strip()]

    @property
    def core_ready(self):
        """Ядро заполнено — можно что-то генерировать."""
        return not self.missing(PROFILE_CORE)

    @property
    def completeness(self):
        """Процент заполненности по всем полям — для индикатора в кабинете."""
        return round(100 * (len(PROFILE_KEYS) - len(self.missing(PROFILE_KEYS)))
                     / len(PROFILE_KEYS))

    def next_question(self):
        """Следующее незаполненное поле: сначала ядро, потом остальное."""
        for k in PROFILE_KEYS:
            if not (getattr(self, k) or '').strip():
                return k, PROFILE_QUESTIONS[k]
        return None, None

    def as_prompt(self):
        """Профиль для передачи модели. Пустые поля не отправляем — иначе
        модель начнёт заполнять пробелы правдоподобными выдумками."""
        out = []
        for k in PROFILE_KEYS:
            v = (getattr(self, k) or '').strip()
            if not v:
                continue
            if k == 'stage':
                v = dict(PROFILE_STAGES).get(v, v)
            out.append(f'{PROFILE_LABELS[k]}: {v}')
        return '\n'.join(out)


class ComposeJob(models.Model):
    """Задание на сборку документа, выполняемое в фоне.

    Зачем не напрямую: обращение к модели длится до полуминуты, а Gunicorn
    работает синхронными процессами. Прямой вызов держал бы процесс целиком —
    три одновременные сборки занимали бы все три, и на это время вставал бы
    весь сайт, включая каталог и бронирование. При показе нескольким людям
    сразу это проявилось бы сразу.

    Хранение в базе, а не в кэше: процессов несколько, у каждого свой кэш в
    памяти, и задание, созданное одним, второй бы не увидел. База общая.
    """
    STATUS = [
        ('pending', 'Выполняется'),
        ('done', 'Готово'),
        ('failed', 'Не удалось'),
    ]
    company = models.ForeignKey('Company', on_delete=models.CASCADE,
                                related_name='compose_jobs', verbose_name='Компания')
    fmt = models.CharField('Формат', max_length=32)
    status = models.CharField('Статус', max_length=10, choices=STATUS, default='pending')
    mode = models.CharField('Режим', max_length=10, blank=True)
    blocks = models.JSONField('Блоки', default=list, blank=True)
    gaps = models.JSONField('Чего не хватило', default=list, blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField('Завершено', null=True, blank=True)

    class Meta:
        verbose_name = 'Сборка документа'
        verbose_name_plural = 'Сборки документов'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.fmt} — {self.get_status_display()}'

    @property
    def stale(self):
        """Задание, о котором никто не отчитался. Процесс мог быть перезапущен
        посреди работы — тогда статус так и остался бы «выполняется» навсегда."""
        limit = settings.COMPOSE_TIMEOUT + 30
        return (self.status == 'pending'
                and (timezone.now() - self.created_at).total_seconds() > limit)


# ==========================================================================
#  СМЕТА ПРОЕКТА — позиции каталога, заложенные в заявку
# ==========================================================================
# Замысел: резидент приходит за помощью с заявкой, а уходит с бронированием.
# Смета — промежуточное звено: список позиций каталога с реальными ценами,
# который одновременно идёт в заявку как статья расходов и превращается
# в бронь, когда грант получен.

# Верхняя граница на количество в строке. Смысл не в деньгах — смета ничего
# не списывает, — а в том, чтобы арифметика оставалась конечной: без предела
# одна опечатка в поле количества выдаёт в итог заявки триллионы.
MAX_BUDGET_QTY = 9999


class BudgetLine(models.Model):
    """Строка сметы: позиция каталога, заложенная в заявку на программу."""
    profile = models.ForeignKey('ProjectProfile', on_delete=models.CASCADE,
                                related_name='budget', verbose_name='Профиль проекта')
    # SET_NULL, а не PROTECT и не CASCADE: снятая с каталога позиция не должна
    # ни блокировать оператору правку каталога, ни молча исчезать из сметы —
    # исчезнув, она изменила бы итог заявки за спиной у резидента.
    resource = models.ForeignKey('Resource', null=True, blank=True,
                                 on_delete=models.SET_NULL,
                                 related_name='budget_lines', verbose_name='Позиция каталога')
    # Слепок на случай, если позицию снимут с каталога: строку всё равно надо
    # чем-то подписать и во что-то оценить.
    title = models.CharField('Наименование', max_length=200)
    unit_price = models.PositiveIntegerField('Цена за единицу, ₽', default=0)
    price_unit = models.CharField('Единица', max_length=20, blank=True)

    qty = models.PositiveIntegerField('Количество', default=1)
    note = models.CharField('Зачем в проекте', max_length=300, blank=True,
                            help_text='Одной строкой — попадёт в заявку как обоснование.')
    created_at = models.DateTimeField('Добавлена', auto_now_add=True)

    class Meta:
        verbose_name = 'Строка сметы'
        verbose_name_plural = 'Смета проекта'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.title} × {self.qty}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.qty and self.qty > MAX_BUDGET_QTY:
            raise ValidationError({'qty': f'Не больше {MAX_BUDGET_QTY} за строку.'})

    def save(self, *args, **kwargs):
        # Цена берётся из каталога при каждом сохранении: каталог — источник
        # правды, а не то, что когда-то скопировали в смету. Если позиции
        # больше нет, остаётся последняя известная цена — иначе строка
        # обнулилась бы и итог заявки поехал бы вниз незаметно.
        if self.resource_id:
            self.title = self.resource.title
            self.unit_price = self.resource.price_value
            self.price_unit = self.resource.price_unit
        super().save(*args, **kwargs)

    @property
    def total(self):
        return self.unit_price * (self.qty or 1)

    @property
    def in_catalog(self):
        return self.resource_id is not None


# ==========================================================================
#  ПРОГРАММЫ ПОДДЕРЖКИ — проверка на формальные отказы
# ==========================================================================
# Большая часть заявок отсеивается не по существу, а по формальным причинам:
# просрочен срок, не тот ОКВЭД, компания старше или больше, чем допускает
# программа, смета выше лимита. Всё это проверяется арифметикой, поэтому
# проверку делает код, а не языковая модель: у правила должен быть один
# ответ, одинаковый при каждом запуске, и его можно предъявить.
#
# Параметры программ вносит оператор в CRM из официальной документации.
# Ни одна программа не заведена в коде намеренно: выдуманный лимит гранта
# выглядит достоверно и потому опаснее пустого списка.

class Program(models.Model):
    """Программа поддержки и её формальные требования.

    Все ограничения необязательны. Пустое поле означает «программа этого не
    ограничивает», а не «ограничение равно нулю» — поэтому именно null,
    а не 0 по умолчанию.
    """
    name = models.CharField('Программа', max_length=200)
    fund = models.CharField('Кто проводит', max_length=200, blank=True)
    url = models.URLField('Страница программы', blank=True)
    active = models.BooleanField('Показывать резидентам', default=True)

    opens_at = models.DateField('Приём заявок с', null=True, blank=True)
    deadline = models.DateField('Приём заявок до', null=True, blank=True)

    max_grant = models.BigIntegerField('Предельный размер гранта, ₽', null=True, blank=True)
    cofinancing_pct = models.PositiveSmallIntegerField(
        'Требуемое софинансирование, %', null=True, blank=True,
        help_text='Доля от суммы гранта, которую заявитель вкладывает сам.')

    min_age_months = models.PositiveIntegerField(
        'Компания не моложе, мес.', null=True, blank=True)
    max_age_months = models.PositiveIntegerField(
        'Компания не старше, мес.', null=True, blank=True)
    max_staff = models.PositiveIntegerField('Численность не более', null=True, blank=True)
    max_revenue = models.BigIntegerField('Выручка не более, ₽', null=True, blank=True)

    okved = models.CharField(
        'Допустимые ОКВЭД', max_length=300, blank=True,
        help_text='Коды или их начала через запятую, напр. «72, 21.20». '
                  'Пусто — программа не ограничивает.')
    stages = models.CharField(
        'Допустимые стадии проекта', max_length=200, blank=True,
        help_text='Ключи стадий через запятую: '
                  + ', '.join(k for k, _ in PROFILE_STAGES) + '. Пусто — любые.')

    notes = models.TextField('Примечания для резидента', blank=True,
                             help_text='Показывается в кабинете как есть.')

    class Meta:
        verbose_name = 'Программа поддержки'
        verbose_name_plural = 'Программы поддержки'
        ordering = ['deadline', 'name']

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.opens_at and self.deadline and self.opens_at > self.deadline:
            errors['deadline'] = 'Срок приёма заканчивается раньше, чем начинается.'
        if (self.min_age_months is not None and self.max_age_months is not None
                and self.min_age_months > self.max_age_months):
            errors['max_age_months'] = 'Верхняя граница возраста меньше нижней.'
        allowed = {k for k, _ in PROFILE_STAGES}
        bad = [s for s in self.stage_list() if s not in allowed]
        if bad:
            errors['stages'] = 'Неизвестные стадии: ' + ', '.join(bad)
        if errors:
            raise ValidationError(errors)

    def stage_list(self):
        return [s.strip() for s in self.stages.split(',') if s.strip()]

    def okved_list(self):
        return [s.strip() for s in self.okved.split(',') if s.strip()]
