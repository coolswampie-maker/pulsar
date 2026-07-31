from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView

from .assist import assist
from .models import KPI_KEYS, BusySlot, CustomRequest, Kpi, KpiEntry, Order, Resource
from .serializers import (CompanySerializer, CustomRequestSerializer,
                          KpiEntrySerializer, KpiSerializer,
                          OrderCreateSerializer, OrderListSerializer, RegisterSerializer,
                          ResourceSerializer)


def _auth_payload(company):
    token, _ = Token.objects.get_or_create(user=company.user)
    return {'token': token.key, 'company': CompanySerializer(company).data}


# ---------- каталог ----------
class ResourceViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/resources/ и /api/resources/<slug>/ — каталог для фронта."""
    queryset = Resource.objects.filter(is_active=True)
    serializer_class = ResourceSerializer
    lookup_field = 'slug'
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        t = self.request.query_params.get('type')
        return qs.filter(type=t) if t else qs

    @action(detail=True, methods=['get'])
    def busy(self, request, slug=None):
        """GET /api/resources/<slug>/busy/ — занятые слоты (общий календарь)."""
        slots = BusySlot.objects.filter(resource_id=slug).values('date', 'slot_start', 'slot_end')
        return Response([
            {'date': str(s['date']),
             'slotStart': s['slot_start'].strftime('%H:%M') if s['slot_start'] else None,
             'slotEnd': s['slot_end'].strftime('%H:%M') if s['slot_end'] else None}
            for s in slots])


class AllBusyView(APIView):
    """GET /api/busy/ — вся занятость по всем ресурсам: {slug: [{date, slotStart, slotEnd}]}.
    Фронт забирает один раз при загрузке, чтобы показывать доступность в каталоге и календаре."""
    permission_classes = [AllowAny]

    def get(self, request):
        out = {}
        for s in BusySlot.objects.values('resource_id', 'date', 'slot_start', 'slot_end'):
            out.setdefault(s['resource_id'], []).append({
                'date': str(s['date']),
                'slotStart': s['slot_start'].strftime('%H:%M') if s['slot_start'] else None,
                'slotEnd': s['slot_end'].strftime('%H:%M') if s['slot_end'] else None,
            })
        return Response(out)


class AssistThrottle(AnonRateThrottle):
    scope = 'assist'


class CustomRequestThrottle(AnonRateThrottle):
    """Отдельный лимит для индивидуальных заявок.

    Раньше форма делила лимит с подбором — и человек, перебравший несколько
    формулировок в подборе, упирался в отказ ровно на той форме, к которой
    подбор его и отправлял. Заявка — редкое действие, ей нужен свой запас.
    """
    scope = 'custom_request'


class AssistView(APIView):
    """POST /api/assist/ — подбор позиций по задаче, описанной словами.

    Принимает {"query": "нужно определить примеси в субстанции"} и возвращает
    до четырёх позиций каталога с коротким обоснованием. Поле "mode" говорит,
    чем подобрано: "ai" — моделью, "local" — встроенным алгоритмом (модель не
    настроена или недоступна). Позиции всегда реальные: идентификаторы от
    модели сверяются с каталогом, несуществующие отбрасываются.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AssistThrottle]

    def post(self, request):
        query = request.data.get('query') if isinstance(request.data, dict) else None
        query = (query or '').strip()
        if not query:
            return Response({'detail': 'Опишите задачу.'}, status=400)

        resources = list(Resource.objects.filter(is_active=True))
        picked, mode, reply = assist(query, resources)
        return Response({
            'mode': mode,
            'reply': reply,
            'items': [{
                'id': r.slug,
                'type': r.type,
                'title': r.title,
                'lab': r.lab,
                'priceValue': r.price_value,
                'priceUnit': r.price_unit,
                'why': why,
            } for r, why in picked],
        })


# ---------- заявки ----------
class OrderViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """POST /api/orders/ — оформить заявку. GET /api/orders/ — заявки своей компании."""
    queryset = Order.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        return OrderListSerializer if self.action == 'list' else OrderCreateSerializer

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        if company:
            return (Order.objects.filter(company=company)
                    .prefetch_related('lines__resource').order_by('-created_at'))
        return Order.objects.none()

    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'detail': 'Требуется вход.'}, status=401)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        ser = OrderCreateSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        order = ser.save()
        # Отдаём итоговые суммы: скидку резидента считает сервер, поэтому экран
        # подтверждения должен показывать её цифры, а не расчёт корзины.
        return Response({'ok': True, 'id': order.number,
                         'subtotal': order.subtotal, 'discount': order.discount,
                         'total': order.total, 'resident': order.resident,
                         'status': order.status}, status=201)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """POST /api/orders/<id>/cancel/ — компания отменяет свою новую заявку."""
        if not request.user.is_authenticated:
            return Response({'detail': 'Требуется вход.'}, status=401)
        order = self.get_queryset().filter(pk=pk).first()
        if not order:
            return Response({'detail': 'Заявка не найдена.'}, status=404)
        if order.status != 'new':
            return Response({'detail': 'Отменить можно только новую заявку.'}, status=400)
        order.delete()
        return Response({'ok': True})

    @action(detail=True, methods=['post'], url_path='request-change')
    def request_change(self, request, pk=None):
        """POST /api/orders/<id>/request-change/ — компания просит оператора изменить даты/время."""
        if not request.user.is_authenticated:
            return Response({'detail': 'Требуется вход.'}, status=401)
        order = self.get_queryset().filter(pk=pk).first()
        if not order:
            return Response({'detail': 'Заявка не найдена.'}, status=404)
        msg = (request.data.get('message') or '').strip()
        if not msg:
            return Response({'detail': 'Опишите, что изменить.'}, status=400)
        order.change_request = msg
        order.save(update_fields=['change_request'])
        return Response({'ok': True, 'changeRequest': msg})


class CustomRequestView(APIView):
    """POST /api/custom-request/ — индивидуальная заявка на подбор.

    Клиент ничего не нашёл в каталоге и описывает потребность словами.
    Гость указывает контакты сам; у вошедшей компании они берутся из профиля.
    Форма публичная, поэтому частота ограничена — но своим счётчиком.
    """
    permission_classes = [AllowAny]
    throttle_classes = [CustomRequestThrottle]

    def post(self, request):
        ser = CustomRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        company = getattr(getattr(request, 'user', None), 'company', None)
        if company:
            org = company.name
            contact = company.contact_name
            email = company.user.email
            phone = company.phone
        else:
            org = (d.get('org') or '').strip()
            contact = (d.get('contact_name') or '').strip()
            email = (d.get('email') or '').strip()
            phone = (d.get('phone') or '').strip()
            if not contact or not (email or phone):
                return Response(
                    {'detail': 'Укажите контактное лицо и e-mail или телефон — '
                               'иначе мы не сможем ответить.'}, status=400)

        req = CustomRequest.objects.create(
            company=company, org=org, contact_name=contact, email=email, phone=phone,
            need=d['need'], period=(d.get('period') or '').strip()[:200],
            search_query=(d.get('search_query') or '').strip()[:300])
        return Response({'ok': True, 'id': req.number}, status=201)


# ---------- авторизация компании ----------
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        company = ser.save()
        return Response(_auth_payload(company), status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user = authenticate(username=request.data.get('email'), password=request.data.get('password'))
        if user is None or not hasattr(user, 'company'):
            return Response({'detail': 'Неверный e-mail или пароль.'}, status=400)
        return Response(_auth_payload(user.company))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def _company(self, request):
        return getattr(request.user, 'company', None)

    def get(self, request):
        company = self._company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        return Response(CompanySerializer(company).data)

    def patch(self, request):
        company = self._company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        ser = CompanySerializer(company, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


# ---------- показатели (KPI по методологии) ----------
def _kpi_company(request):
    return getattr(request.user, 'company', None)


def _kpi_year(request):
    try:
        y = int(request.query_params.get('year') or 0)
    except (TypeError, ValueError):
        y = 0
    return y or timezone.localdate().year


class KpiView(APIView):
    """GET /api/kpi/?year= — 6 показателей компании за год (автосоздание)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = _kpi_company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        year = _kpi_year(request)
        existing = {k.key: k for k in company.kpis.filter(year=year)}
        for key in KPI_KEYS:
            if key not in existing:
                existing[key] = Kpi.objects.create(company=company, year=year, key=key)
        items = [existing[key] for key in KPI_KEYS]
        return Response({'year': year, 'items': KpiSerializer(items, many=True, context={'request': request}).data})


def _extract_from_pdf(f):
    """Эвристика: заголовок + первое денежное число из PDF. Умное распознавание —
    LLM (Qwen) на Yandex Cloud. Возвращает (title, amount)."""
    import io
    import re
    title, amount = None, None
    try:
        data = f.read()
        f.seek(0)
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = '\n'.join((p.extract_text() or '') for p in reader.pages[:3])
        for line in text.splitlines():
            line = line.strip()
            if len(line) > 4:
                title = line[:120]
                break
        m = re.search(r'(\d[\d\s]{2,}(?:[.,]\d+)?)\s*(?:руб|₽|р\.)', text.replace('\xa0', ' '))
        if m:
            amount = m.group(1).replace(' ', '').replace(',', '.')
    except Exception:
        pass
    return title, amount


class KpiEntriesView(APIView):
    """POST /api/kpi/<key>/entries/?year= — добавить позицию (вручную, можно с документом)."""
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request, key):
        company = _kpi_company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        if key not in KPI_KEYS:
            return Response({'detail': 'Неизвестный показатель.'}, status=404)
        year = _kpi_year(request)
        kpi, _ = Kpi.objects.get_or_create(company=company, year=year, key=key)
        ser = KpiEntrySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(kpi=kpi, source='manual')
        return Response(ser.data, status=201)


class KpiEntryView(APIView):
    """DELETE /api/kpi/<key>/entries/<id>/ — удалить позицию."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, key, entry_id):
        company = _kpi_company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        entry = KpiEntry.objects.filter(pk=entry_id, kpi__company=company, kpi__key=key).first()
        if not entry:
            return Response({'detail': 'Позиция не найдена.'}, status=404)
        entry.delete()
        return Response(status=204)


class KpiExtractView(APIView):
    """POST /api/kpi/<key>/extract/?year= — прикрепить PDF, система заводит позицию.
    Сейчас — эвристика + прикреплённый файл; умное распознавание ИИ подключается на деплое."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, key):
        company = _kpi_company(request)
        if not company:
            return Response({'detail': 'Нет профиля компании.'}, status=404)
        if key not in KPI_KEYS:
            return Response({'detail': 'Неизвестный показатель.'}, status=404)
        f = request.FILES.get('document')
        if not f:
            return Response({'detail': 'Прикрепите файл.'}, status=400)
        # тот же фильтр форматов, что и при обычном добавлении позиции
        from rest_framework.exceptions import ValidationError as DRFValidationError

        from .serializers import validate_document
        try:
            validate_document(f)
        except DRFValidationError as e:
            return Response({'detail': ' '.join(map(str, e.detail))}, status=400)
        year = _kpi_year(request)
        kpi, _ = Kpi.objects.get_or_create(company=company, year=year, key=key)
        title, amount = _extract_from_pdf(f)
        entry = KpiEntry.objects.create(kpi=kpi, title=(title or f.name)[:300],
                                        amount=amount, document=f, source='auto')
        return Response(KpiEntrySerializer(entry).data, status=201)
