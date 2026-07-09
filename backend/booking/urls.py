from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (KpiEntriesView, KpiEntryView, KpiExtractView, KpiView, LoginView,
                    MeView, OrderViewSet, RegisterView, ResourceViewSet)

router = DefaultRouter()
router.register('resources', ResourceViewSet, basename='resource')
router.register('orders', OrderViewSet, basename='order')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('kpi/', KpiView.as_view(), name='kpi'),
    path('kpi/<str:key>/entries/', KpiEntriesView.as_view(), name='kpi-entries'),
    path('kpi/<str:key>/entries/<int:entry_id>/', KpiEntryView.as_view(), name='kpi-entry'),
    path('kpi/<str:key>/extract/', KpiExtractView.as_view(), name='kpi-extract'),
] + router.urls
