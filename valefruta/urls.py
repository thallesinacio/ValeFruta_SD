from django.contrib import admin
from django.urls import path

admin.site.site_header = "ValeFruta | Administração"
admin.site.site_title = "ValeFruta Admin"
admin.site.index_title = "Painel de gestão da vitrine de produtores"

urlpatterns = [
    path("admin/", admin.site.urls),
]
