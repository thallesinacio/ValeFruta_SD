from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "ValeFruta | Administração"
admin.site.site_title = "ValeFruta Admin"
admin.site.index_title = "Painel de gestão da vitrine de produtores"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="lista_lotes", permanent=False)),
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("lotes/", include("produtores.urls")),
]
