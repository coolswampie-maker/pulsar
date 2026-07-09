from django.contrib.auth import authenticate
from rest_framework import mixins, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BusySlot, Order, Resource
from .serializers import (CompanySerializer, OrderCreateSerializer, OrderListSerializer,
                          RegisterSerializer, ResourceSerializer)


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
        return Response({'ok': True, 'id': order.number}, status=201)


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
