from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'ПУЛЬСАР — оператор'
admin.site.site_title = 'ПУЛЬСАР'
admin.site.index_title = 'Управление инфраструктурой и бронями'

urlpatterns = [
    path('admin/', admin.site.urls),        # CRM оператора (заявки + карточки оборудования)
    path('api/', include('booking.urls')),  # API для фронта
]
