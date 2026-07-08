from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, ResourceViewSet

router = DefaultRouter()
router.register('resources', ResourceViewSet, basename='resource')
router.register('orders', OrderViewSet, basename='order')

urlpatterns = router.urls
