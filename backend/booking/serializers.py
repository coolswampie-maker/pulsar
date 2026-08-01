from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (KPI_META, PROFILE_STAGES, BookingLine, Company, CustomRequest, Kpi,
                     KpiEntry, Order, ProjectProfile, Resource)

User = get_user_model()


# Подтверждающие документы отдаются с того же домена, что и сайт, поэтому
# загружать можно только форматы, которые браузер не исполнит. HTML/SVG/JS
# на своём домене — это чужой скрипт в кабинете оператора.
# Потолок на количество образцов в одной позиции услуги «под ключ».
# Не физическое ограничение, а защита от опечатки и от заявки-шутки:
# партия больше сотни всё равно согласуется с оператором отдельно.
MAX_SAMPLE_QTY = 100

DOC_EXTS = ('pdf', 'jpg', 'jpeg', 'png', 'webp', 'heic',
            'doc', 'docx', 'xls', 'xlsx', 'odt', 'ods', 'rtf', 'txt', 'zip', 'rar', '7z')
DOC_MAX_MB = 25


def validate_document(f):
    """Проверка загружаемого документа: расширение и размер."""
    if not f:
        return f
    import os
    ext = os.path.splitext(getattr(f, 'name', '') or '')[1].lower().lstrip('.')
    if ext not in DOC_EXTS:
        raise serializers.ValidationError(
            'Недопустимый формат файла. Разрешены: ' + ', '.join(DOC_EXTS) + '.')
    if getattr(f, 'size', 0) > DOC_MAX_MB * 1024 * 1024:
        raise serializers.ValidationError(f'Файл больше {DOC_MAX_MB} МБ.')
    return f


class KpiEntrySerializer(serializers.ModelSerializer):
    """Позиция показателя: что сделано / на что потрачено."""
    class Meta:
        model = KpiEntry
        fields = ('id', 'title', 'amount', 'date', 'document', 'source', 'created_at')
        read_only_fields = ('id', 'source', 'created_at')

    def validate_document(self, f):
        return validate_document(f)


class KpiSerializer(serializers.ModelSerializer):
    """Показатель: план (оператор), факт из позиций, значение (для долей — % от выручки)."""
    label = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    hint = serializers.SerializerMethodField()
    docs = serializers.SerializerMethodField()
    status = serializers.ReadOnlyField()
    value = serializers.ReadOnlyField()
    percent = serializers.SerializerMethodField()
    entries = KpiEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Kpi
        fields = ('key', 'label', 'unit', 'hint', 'docs', 'plan', 'fact', 'value',
                  'percent', 'status', 'entries', 'updated_at', 'year')
        read_only_fields = ('key', 'plan', 'fact', 'year', 'updated_at')

    def get_label(self, o): return KPI_META[o.key]['label']
    def get_unit(self, o): return KPI_META[o.key]['unit']
    def get_hint(self, o): return KPI_META[o.key]['hint']
    def get_docs(self, o): return KPI_META[o.key]['docs']
    def get_percent(self, o): return o.key in Kpi.PERCENT_KEYS


class CompanySerializer(serializers.ModelSerializer):
    """Профиль компании для личного кабинета."""
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Company
        fields = ('name', 'inn', 'category', 'resident', 'confirmed',
                  'contact_name', 'phone', 'email', 'created_at')
        read_only_fields = ('created_at', 'email', 'resident', 'confirmed')


class RegisterSerializer(serializers.Serializer):
    """Регистрация компании. Минимум полей; остальное и статус резидента
    заполняет оператор при подтверждении."""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)

    def validate_email(self, v):
        if User.objects.filter(username=v).exists():
            raise serializers.ValidationError('Компания с таким e-mail уже зарегистрирована.')
        return v

    def validate_password(self, v):
        # прогоняем через AUTH_PASSWORD_VALIDATORS: длина, словарь утечек,
        # «только цифры», похожесть на e-mail. create_user их сам не проверяет.
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(v)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return v

    def create(self, validated):
        user = User.objects.create_user(
            username=validated['email'], email=validated['email'], password=validated['password'])
        # resident/confirmed по умолчанию False — подтверждает оператор
        return Company.objects.create(
            user=user, name=validated['name'], phone=validated.get('phone', ''))


class LineOutSerializer(serializers.ModelSerializer):
    resourceId = serializers.CharField(source='resource_id')
    title = serializers.CharField(source='resource.title', read_only=True)
    type = serializers.CharField(source='resource.type', read_only=True)
    slotStart = serializers.TimeField(source='slot_start', format='%H:%M')
    slotEnd = serializers.TimeField(source='slot_end', format='%H:%M')
    linePrice = serializers.IntegerField(source='line_price')
    isOperator = serializers.BooleanField(source='is_operator')

    class Meta:
        model = BookingLine
        fields = ('resourceId', 'title', 'type', 'date', 'slotStart', 'slotEnd',
                  'qty', 'hours', 'linePrice', 'isOperator')


class OrderListSerializer(serializers.ModelSerializer):
    """Заявка компании для раздела «Мои заявки»."""
    lines = LineOutSerializer(many=True, read_only=True)
    statusLabel = serializers.CharField(source='get_status_display', read_only=True)
    changeRequest = serializers.CharField(source='change_request', read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'number', 'status', 'statusLabel', 'created_at', 'org', 'note',
                  'changeRequest', 'subtotal', 'discount', 'total', 'resident', 'lines')


class CustomRequestSerializer(serializers.ModelSerializer):
    """Приём индивидуальной заявки на подбор.

    Контакты для гостя обязательны — иначе оператору некуда отвечать.
    Для вошедшей компании они подставляются из профиля во view.
    """
    class Meta:
        model = CustomRequest
        fields = ('need', 'period', 'search_query', 'org', 'contact_name', 'email', 'phone')
        extra_kwargs = {
            'need': {'required': True, 'allow_blank': False},
            'period': {'required': False, 'allow_blank': True},
            'search_query': {'required': False, 'allow_blank': True},
        }

    def validate_need(self, v):
        v = (v or '').strip()
        if len(v) < 10:
            raise serializers.ValidationError(
                'Опишите подробнее, что требуется — так оператор сможет помочь.')
        return v[:4000]


class ResourceSerializer(serializers.ModelSerializer):
    """Отдаёт ресурс в формате, близком к data/resources.js фронта."""
    id = serializers.CharField(source='slug')
    bookMode = serializers.CharField(source='book_mode')
    priceValue = serializers.IntegerField(source='price_value')
    priceUnit = serializers.CharField(source='price_unit')
    minUnits = serializers.IntegerField(source='min_units')
    cleanClass = serializers.CharField(source='clean_class')
    requiresOperator = serializers.CharField(source='requires_operator_id', allow_null=True)
    bundledWith = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = ('id', 'type', 'category', 'bookMode', 'title', 'lab', 'cleanClass',
                  'description', 'specs', 'priceValue', 'priceUnit', 'minUnits',
                  'image', 'requiresOperator', 'bundledWith')

    def get_bundledWith(self, obj):
        return list(obj.bundled_with.values_list('slug', flat=True))


class BookingLineInSerializer(serializers.Serializer):
    """Позиция заявки от фронта.

    unitPrice/linePrice принимаем только для совместимости и НЕ используем в
    расчётах: цену берём из каталога на сервере (см. BookingLine.save и
    OrderCreateSerializer.create). Иначе можно было бы прислать свою цену.
    """
    resourceId = serializers.CharField()
    date = serializers.DateField(required=False, allow_null=True)
    slotStart = serializers.TimeField(required=False, allow_null=True)
    slotEnd = serializers.TimeField(required=False, allow_null=True)
    qty = serializers.IntegerField(default=1, min_value=1)
    hours = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=24)
    unitPrice = serializers.IntegerField(default=0)
    linePrice = serializers.IntegerField(default=0)
    isOperator = serializers.BooleanField(default=False)


class OrderCreateSerializer(serializers.Serializer):
    """Приём заявки из корзины фронта."""
    contact = serializers.DictField()
    resident = serializers.BooleanField(default=False)
    lines = BookingLineInSerializer(many=True, allow_empty=False)

    def validate_lines(self, lines):
        """Проверяем то, что влияет на деньги и на реальную доступность.

        Полный BookingLine.clean() здесь применить нельзя: ночная смена
        лаборатории (18:00–02:00) законно выходит за рабочие часы и «заканчивается
        раньше, чем начинается», поэтому проверяем выборочно.
        """
        from django.utils import timezone
        today = timezone.localdate()
        slugs = {l['resourceId'] for l in lines}
        found = {r.slug: r for r in Resource.objects.filter(slug__in=slugs, is_active=True)}
        errors = []
        for i, l in enumerate(lines):
            res = found.get(l['resourceId'])
            if not res:
                errors.append(f'Позиция {i + 1}: ресурс «{l["resourceId"]}» не найден или снят с публикации.')
                continue
            # У услуг «под ключ» qty — это количество образцов, а не одновременно
            # занятых единиц, поэтому наличием оно не ограничено. Но и без
            # потолка оставлять нельзя: аудит показал, что 9999 образцов
            # принимались молча и давали заявку на 34 миллиона. Партию больше
            # сотни всё равно согласовывают с оператором отдельно.
            if res.book_mode == 'sample':
                if l.get('qty', 1) > MAX_SAMPLE_QTY:
                    errors.append(
                        f'Позиция {i + 1}: за раз принимаем до {MAX_SAMPLE_QTY} образцов. '
                        f'Для большей партии оставьте индивидуальную заявку.')
            else:
                if l.get('qty', 1) > res.units_total:
                    errors.append(f'Позиция {i + 1}: доступно единиц — {res.units_total}.')
                # услуги бронируются без даты, остальное — только не в прошлом
                if not l.get('date'):
                    errors.append(f'Позиция {i + 1}: не указана дата.')
                elif l['date'] < today:
                    errors.append(f'Позиция {i + 1}: дата в прошлом.')
        if errors:
            raise serializers.ValidationError(errors)
        return lines

    def create(self, validated):
        from django.db import transaction
        c = validated['contact']
        lines = validated['lines']
        # компания из ЛК, если запрос авторизован
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None) if request else None
        # Скидка резидента — только компаниям, которых оператор подтвердил как
        # резидентов ИНТЦ. Галочка в корзине — лишь заявление о статусе: гость не
        # может выдать себе 25% сам. Непроверенное заявление уходит оператору
        # пометкой в комментарии — он сверит статус и при необходимости
        # проставит скидку в заявке вручную.
        resident = bool(company and company.resident and company.confirmed)
        claimed = bool(validated['resident'])
        note = c.get('note', '')
        if claimed and not resident:
            mark = 'Заявлен статус резидента ИНТЦ — требуется проверка оператором.'
            note = (note + '\n' + mark).strip() if note else mark
        with transaction.atomic():
            number = Order.next_number()
            order = Order.objects.create(
                number=number, company=company,
                org=(company.name if company else c.get('org', '')),
                contact_name=(company.contact_name if company else c.get('name', '')),
                email=(company.user.email if company else c.get('email', '')),
                phone=(company.phone if company else c.get('phone', '')),
                note=note, resident=resident, subtotal=0, discount=0, total=0)
            for l in lines:
                # unit_price/line_price сознательно не берём из запроса:
                # BookingLine.save() считает их по цене ресурса из каталога.
                BookingLine.objects.create(
                    order=order, resource_id=l['resourceId'], date=l.get('date'),
                    slot_start=l.get('slotStart'), slot_end=l.get('slotEnd'),
                    qty=l.get('qty', 1), hours=l.get('hours'),
                    is_operator=l.get('isOperator', False))
            # Итог считаем по сохранённым строкам, а не по присланным суммам —
            # иначе можно оформить бронь за любую цену, вплоть до рубля.
            subtotal = sum(order.lines.values_list('line_price', flat=True))
            discount = round(subtotal * 0.25) if resident else 0
            order.subtotal, order.discount, order.total = subtotal, discount, subtotal - discount
            order.save(update_fields=['subtotal', 'discount', 'total'])
        return order


class ProjectProfileSerializer(serializers.ModelSerializer):
    """Профиль проекта: всё необязательно, заполняется по частям."""
    completeness = serializers.IntegerField(read_only=True)
    coreReady = serializers.BooleanField(source='core_ready', read_only=True)

    class Meta:
        model = ProjectProfile
        fields = ('title', 'summary', 'problem', 'solution', 'stage', 'groundwork',
                  'team', 'market', 'competitors', 'business_model', 'workplan',
                  'risks', 'needs', 'completeness', 'coreReady', 'updated_at')
        read_only_fields = ('updated_at',)

    def validate_stage(self, v):
        if v and v not in dict(PROFILE_STAGES):
            raise serializers.ValidationError('Неизвестная стадия готовности.')
        return v
