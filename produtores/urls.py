from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista_lotes, name="lista_lotes"),
    path("novo/", views.novo_lote, name="novo_lote"),
]
