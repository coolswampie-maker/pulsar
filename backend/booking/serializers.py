from rest_framework import serializers

from .models import BookingLine, Order, Resource


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
        discount = round(subtotal * 0.25) if validated['resident'] else 0
        with transaction.atomic():
            number = 'PLS-' + str(1000 + Order.objects.count() + 1)
            order = Order.objects.create(
                number=number, org=c.get('org', ''), contact_name=c.get('name', ''),
                email=c.get('email', ''), phone=c.get('phone', ''), note=c.get('note', ''),
                resident=validated['resident'], subtotal=subtotal, discount=discount,
                total=subtotal - discount)
            for l in lines:
                BookingLine.objects.create(
                    order=order, resource_id=l['resourceId'], date=l.get('date'),
                    slot_start=l.get('slotStart'), slot_end=l.get('slotEnd'),
                    qty=l.get('qty', 1), hours=l.get('hours'),
                    unit_price=l.get('unitPrice', 0), line_price=l.get('linePrice', 0),
                    is_operator=l.get('isOperator', False))
        return order
