from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import LoginView, MeView, OrderViewSet, RegisterView, ResourceViewSet

router = DefaultRouter()
router.register('resources', ResourceViewSet, basename='resource')
router.register('orders', OrderViewSet, basename='order')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
] + router.urls
