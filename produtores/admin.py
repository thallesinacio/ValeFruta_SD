from django.contrib import admin
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Sum
from django.urls import reverse
from django.utils.html import format_html

from .models import Certificacao, Cultura, Lote, Produtor, Propriedade


def link_admin(obj, texto=None):
    """Link para a página de edição de um objeto no admin."""
    if obj is None:
        return "-"
    url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
    return format_html('<a href="{}">{}</a>', url, texto or obj)


def brl(valor):
    """Formata um número como moeda brasileira (R$ 1.234,56)."""
    if valor is None:
        return "-"
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


# --------------------------------------------------------------------------- #
# Inlines (refletem as relações de dependência)
# --------------------------------------------------------------------------- #

class PropriedadeInline(admin.TabularInline):
    """Propriedades exibidas dentro do Produtor (Produtor 1 → N Propriedade)."""

    model = Propriedade
    extra = 0
    fields = ("nome", "municipio", "uf", "area_hectares", "tipo_irrigacao")
    show_change_link = True


class LoteInline(admin.TabularInline):
    """Lotes exibidos dentro da Propriedade (Propriedade 1 → N Lote)."""

    model = Lote
    extra = 0
    fields = ("codigo", "cultura", "classificacao", "quantidade_kg",
              "quantidade_disponivel_kg", "preco_kg", "data_colheita", "status")
    autocomplete_fields = ("cultura",)
    show_change_link = True
    ordering = ("-data_colheita",)


class LoteDaCulturaInline(admin.TabularInline):
    """Lotes de uma cultura, somente leitura (Cultura 1 → N Lote)."""

    model = Lote
    extra = 0
    fields = ("codigo", "propriedade", "quantidade_disponivel_kg", "preco_kg", "status")
    readonly_fields = fields
    show_change_link = True
    can_delete = False
    max_num = 0
    verbose_name_plural = "lotes desta cultura (somente leitura)"


# --------------------------------------------------------------------------- #
# Catálogos
# --------------------------------------------------------------------------- #

@admin.register(Certificacao)
class CertificacaoAdmin(admin.ModelAdmin):
    list_display = ("sigla", "nome", "orgao_emissor", "exigida_exportacao", "total_propriedades")
    list_filter = ("exigida_exportacao",)
    search_fields = ("sigla", "nome", "orgao_emissor")
    ordering = ("sigla",)
    list_per_page = 25

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_props=Count("propriedades", distinct=True))

    @admin.display(description="propriedades certificadas", ordering="_props")
    def total_propriedades(self, obj):
        return obj._props


@admin.register(Cultura)
class CulturaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "fruta", "variedade", "ciclo_dias", "perene",
                    "total_propriedades", "total_lotes", "preco_medio_kg")
    list_filter = ("fruta", "perene")
    search_fields = ("variedade", "fruta", "nome_cientifico")
    ordering = ("fruta", "variedade")
    list_per_page = 50
    fieldsets = (
        ("Identificação", {"fields": ("fruta", "variedade", "nome_cientifico")}),
        ("Cultivo", {"fields": ("ciclo_dias", "perene", "descricao")}),
    )
    inlines = [LoteDaCulturaInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _props=Count("propriedades", distinct=True),
            _lotes=Count("lotes", distinct=True),
            _preco=Avg("lotes__preco_kg"),
        )

    @admin.display(description="propriedades", ordering="_props")
    def total_propriedades(self, obj):
        return obj._props

    @admin.display(description="lotes", ordering="_lotes")
    def total_lotes(self, obj):
        return obj._lotes

    @admin.display(description="preço médio/kg", ordering="_preco")
    def preco_medio_kg(self, obj):
        return brl(obj._preco)


# --------------------------------------------------------------------------- #
# Produtor e propriedade
# --------------------------------------------------------------------------- #

@admin.register(Produtor)
class ProdutorAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo_pessoa", "documento", "municipio", "uf", "ativo",
                    "total_propriedades", "total_pedidos", "nota_media")
    list_filter = ("ativo", "tipo_pessoa", "uf", "municipio")
    search_fields = ("nome", "documento", "usuario__username", "usuario__email", "municipio")
    ordering = ("nome",)
    list_per_page = 25
    list_editable = ("ativo",)
    autocomplete_fields = ("usuario",)
    readonly_fields = ("data_cadastro",)
    date_hierarchy = "data_cadastro"
    fieldsets = (
        ("Conta", {"fields": ("usuario", "ativo", "data_cadastro")}),
        ("Identificação", {"fields": ("nome", "tipo_pessoa", "documento")}),
        ("Contato e localização", {"fields": ("telefone", "municipio", "uf")}),
        ("Apresentação", {"fields": ("bio",), "classes": ("collapse",)}),
    )
    inlines = [PropriedadeInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _props=Count("propriedades", distinct=True),
            _pedidos=Count("pedidos_recebidos", distinct=True),
            _nota=Avg("pedidos_recebidos__avaliacao__nota"),
        )

    @admin.display(description="propriedades", ordering="_props")
    def total_propriedades(self, obj):
        return obj._props

    @admin.display(description="pedidos recebidos", ordering="_pedidos")
    def total_pedidos(self, obj):
        return obj._pedidos

    @admin.display(description="nota média", ordering="_nota")
    def nota_media(self, obj):
        return f"{obj._nota:.1f} ★" if obj._nota is not None else "-"


@admin.register(Propriedade)
class PropriedadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "produtor_link", "municipio", "uf", "perimetro_irrigado",
                    "area_hectares", "tipo_irrigacao", "total_culturas", "total_lotes")
    list_filter = ("uf", "municipio", "tipo_irrigacao", "certificacoes", "culturas__fruta")
    search_fields = ("nome", "produtor__nome", "municipio", "perimetro_irrigado")
    ordering = ("produtor__nome", "nome")
    list_per_page = 25
    list_select_related = ("produtor",)
    autocomplete_fields = ("produtor",)
    filter_horizontal = ("culturas", "certificacoes")
    fieldsets = (
        ("Identificação", {"fields": ("produtor", "nome")}),
        ("Localização", {"fields": ("municipio", "uf", "perimetro_irrigado", ("latitude", "longitude"))}),
        ("Produção", {"fields": ("area_hectares", "tipo_irrigacao", "culturas", "certificacoes")}),
    )
    inlines = [LoteInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _culturas=Count("culturas", distinct=True),
            _lotes=Count("lotes", distinct=True),
        )

    @admin.display(description="produtor", ordering="produtor__nome")
    def produtor_link(self, obj):
        return link_admin(obj.produtor)

    @admin.display(description="culturas", ordering="_culturas")
    def total_culturas(self, obj):
        return obj._culturas

    @admin.display(description="lotes", ordering="_lotes")
    def total_lotes(self, obj):
        return obj._lotes


# --------------------------------------------------------------------------- #
# Lote
# --------------------------------------------------------------------------- #

@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ("codigo", "cultura", "propriedade_link", "classificacao", "destino",
                    "quantidade_disponivel_kg", "preco_kg", "valor_em_estoque",
                    "total_vendido_kg", "data_colheita", "status")
    list_filter = ("status", "destino", "classificacao", "cultura__fruta",
                   "propriedade__uf", "propriedade__municipio", "data_colheita")
    search_fields = ("codigo", "cultura__variedade", "cultura__fruta",
                     "propriedade__nome", "propriedade__produtor__nome")
    ordering = ("-data_colheita", "codigo")
    list_per_page = 30
    list_select_related = ("cultura", "propriedade")
    autocomplete_fields = ("propriedade", "cultura")
    readonly_fields = ("criado_em", "valor_em_estoque", "total_vendido_kg")
    date_hierarchy = "data_colheita"
    fieldsets = (
        ("Origem", {"fields": ("codigo", "propriedade", "cultura")}),
        ("Qualidade e destino", {"fields": ("classificacao", "destino", "data_colheita", "validade_dias")}),
        ("Estoque e preço", {"fields": (("quantidade_kg", "quantidade_disponivel_kg"), "preco_kg",
                                         "valor_em_estoque", "total_vendido_kg", "status")}),
        ("Outros", {"fields": ("observacoes", "criado_em"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        estoque = ExpressionWrapper(F("quantidade_disponivel_kg") * F("preco_kg"),
                                    output_field=DecimalField(max_digits=14, decimal_places=2))
        return super().get_queryset(request).annotate(
            _estoque=estoque,
            _vendido=Sum("itens_pedido__quantidade_kg"),
        )

    @admin.display(description="propriedade", ordering="propriedade__nome")
    def propriedade_link(self, obj):
        return link_admin(obj.propriedade, obj.propriedade.nome)

    @admin.display(description="valor em estoque", ordering="_estoque")
    def valor_em_estoque(self, obj):
        return brl(getattr(obj, "_estoque", obj.valor_estoque))

    @admin.display(description="vendido (kg)", ordering="_vendido")
    def total_vendido_kg(self, obj):
        return getattr(obj, "_vendido", None) or 0
