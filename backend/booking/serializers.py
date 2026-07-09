from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import KPI_META, BookingLine, Company, Kpi, KpiEntry, Order, Resource

User = get_user_model()


class KpiEntrySerializer(serializers.ModelSerializer):
    """Позиция показателя: что сделано / на что потрачено."""
    class Meta:
        model = KpiEntry
        fields = ('id', 'title', 'amount', 'date', 'document', 'source', 'created_at')
        read_only_fields = ('id', 'source', 'created_at')


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
    password = serializers.CharField(min_length=6, write_only=True)
    name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)

    def validate_email(self, v):
        if User.objects.filter(username=v).exists():
            raise serializers.ValidationError('Компания с таким e-mail уже зарегистрирована.')
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

    class Meta:
        model = Order
        fields = ('id', 'number', 'status', 'statusLabel', 'created_at', 'org', 'note',
                  'subtotal', 'discount', 'total', 'resident', 'lines')


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
    resourceId = serializers.CharField()
    date = serializers.DateField(required=False, allow_null=True)
    slotStart = serializers.TimeField(required=False, allow_null=True)
    slotEnd = serializers.TimeField(required=False, allow_null=True)
    qty = serializers.IntegerField(default=1)
    hours = serializers.IntegerField(required=False, allow_null=True)
    unitPrice = serializers.IntegerField(default=0)
    linePrice = serializers.IntegerField(default=0)
    isOperator = serializers.BooleanField(default=False)


class OrderCreateSerializer(serializers.Serializer):
    """Приём заявки из корзины фронта."""
    contact = serializers.DictField()
    resident = serializers.BooleanField(default=False)
    lines = BookingLineInSerializer(many=True)

    def create(self, validated):
        from django.db import transaction
        c = validated['contact']
        lines = validated['lines']
        subtotal = sum(l['linePrice'] for l in lines)
        # компания из ЛК, если запрос авторизован
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None) if request else None
        # скидка резидента — только для подтверждённых оператором компаний
        resident = (company.resident and company.confirmed) if company else validated['resident']
        discount = round(subtotal * 0.25) if resident else 0
        with transaction.atomic():
            number = Order.next_number()
            order = Order.objects.create(
                number=number, company=company,
                org=(company.name if company else c.get('org', '')),
                contact_name=(company.contact_name if company else c.get('name', '')),
                email=(company.user.email if company else c.get('email', '')),
                phone=(company.phone if company else c.get('phone', '')),
                note=c.get('note', ''),
                resident=resident, subtotal=subtotal, discount=discount,
                total=subtotal - discount)
            for l in lines:
                BookingLine.objects.create(
                    order=order, resource_id=l['resourceId'], date=l.get('date'),
                    slot_start=l.get('slotStart'), slot_end=l.get('slotEnd'),
                    qty=l.get('qty', 1), hours=l.get('hours'),
                    unit_price=l.get('unitPrice', 0), line_price=l.get('linePrice', 0),
                    is_operator=l.get('isOperator', False))
        return order
