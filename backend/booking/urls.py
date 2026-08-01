from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (AllBusyView, AssistView, ComposeFormatsView, ComposeView, CustomRequestView, KpiEntriesView, KpiEntryView, KpiExtractView, KpiView, LoginView, MeView, OrderViewSet, ProfileNextView, ProfileView, RegisterView, ResourceViewSet)

router = DefaultRouter()
router.register('resources', ResourceViewSet, basename='resource')
router.register('orders', OrderViewSet, basename='order')

urlpatterns = [
    path('busy/', AllBusyView.as_view(), name='busy-all'),
    path('assist/', AssistView.as_view(), name='assist'),
    path('custom-request/', CustomRequestView.as_view(), name='custom-request'),
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/next/', ProfileNextView.as_view(), name='profile-next'),
    path('profile/formats/', ComposeFormatsView.as_view(), name='profile-formats'),
    path('profile/compose/', ComposeView.as_view(), name='profile-compose'),
    path('kpi/', KpiView.as_view(), name='kpi'),
    path('kpi/<str:key>/entries/', KpiEntriesView.as_view(), name='kpi-entries'),
    path('kpi/<str:key>/entries/<int:entry_id>/', KpiEntryView.as_view(), name='kpi-entry'),
    path('kpi/<str:key>/extract/', KpiExtractView.as_view(), name='kpi-extract'),
] + router.urls
