from django.contrib import admin
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum

from produtores.admin import brl, link_admin

from .models import Avaliacao, Comprador, CotacaoCambio, ItemPedido, Pedido

SUBTOTAL = ExpressionWrapper(
    F("itens__quantidade_kg") * F("itens__preco_unitario"),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)


# --------------------------------------------------------------------------- #
# Inlines
# --------------------------------------------------------------------------- #

class PedidoInline(admin.TabularInline):
    """Pedidos exibidos dentro do Comprador (Comprador 1 → N Pedido)."""

    model = Pedido
    extra = 0
    fields = ("codigo", "produtor", "status", "data_pedido", "data_entrega_prevista", "forma_pagamento")
    readonly_fields = fields
    show_change_link = True
    can_delete = False
    max_num = 0
    ordering = ("-data_pedido",)
    verbose_name_plural = "pedidos deste comprador (abra o pedido para editar)"


class ItemPedidoInline(admin.TabularInline):
    """Itens dentro do Pedido (Pedido 1 → N ItemPedido)."""

    model = ItemPedido
    extra = 0
    fields = ("lote", "quantidade_kg", "preco_unitario", "subtotal_item")
    readonly_fields = ("subtotal_item",)
    autocomplete_fields = ("lote",)

    @admin.display(description="subtotal")
    def subtotal_item(self, obj):
        return brl(obj.subtotal) if obj.pk else "-"


class AvaliacaoInline(admin.StackedInline):
    """Avaliação dentro do Pedido (Pedido 1 → 1 Avaliacao)."""

    model = Avaliacao
    extra = 0
    max_num = 1
    fields = (("nota", "qualidade_fruta", "pontualidade"), "comentario", "criada_em")
    readonly_fields = ("criada_em",)


# --------------------------------------------------------------------------- #
# Comprador
# --------------------------------------------------------------------------- #

@admin.register(Comprador)
class CompradorAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "documento", "municipio", "uf", "total_pedidos", "total_comprado")
    list_filter = ("tipo", "tipo_pessoa", "uf", "municipio")
    search_fields = ("nome", "documento", "usuario__username", "usuario__email", "municipio")
    ordering = ("nome",)
    list_per_page = 25
    autocomplete_fields = ("usuario",)
    readonly_fields = ("data_cadastro",)
    date_hierarchy = "data_cadastro"
    fieldsets = (
        ("Conta", {"fields": ("usuario", "data_cadastro")}),
        ("Identificação", {"fields": ("nome", "tipo", "tipo_pessoa", "documento")}),
        ("Contato e endereço", {"fields": ("telefone", "endereco", ("municipio", "uf"))}),
    )
    inlines = [PedidoInline]

    def get_queryset(self, request):
        subtotal = ExpressionWrapper(
            F("pedidos__itens__quantidade_kg") * F("pedidos__itens__preco_unitario"),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
        return super().get_queryset(request).annotate(
            _pedidos=Count("pedidos", distinct=True),
            _total=Sum(subtotal),
        )

    @admin.display(description="pedidos", ordering="_pedidos")
    def total_pedidos(self, obj):
        return obj._pedidos

    @admin.display(description="total comprado", ordering="_total")
    def total_comprado(self, obj):
        return brl(obj._total)


# --------------------------------------------------------------------------- #
# Pedido
# --------------------------------------------------------------------------- #

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "comprador_link", "produtor_link", "status", "forma_pagamento",
                    "data_pedido", "qtd_itens", "valor_total_display", "tem_avaliacao")
    list_filter = ("status", "forma_pagamento", "data_pedido", "comprador__tipo", "produtor__uf")
    search_fields = ("codigo", "comprador__nome", "produtor__nome", "endereco_entrega")
    ordering = ("-data_pedido",)
    list_per_page = 30
    list_select_related = ("comprador", "produtor", "avaliacao")
    autocomplete_fields = ("comprador", "produtor")
    readonly_fields = ("valor_itens_display", "valor_total_display")
    date_hierarchy = "data_pedido"
    fieldsets = (
        ("Partes", {"fields": ("codigo", "comprador", "produtor")}),
        ("Andamento", {"fields": ("status", "data_pedido", "data_entrega_prevista", "data_entrega")}),
        ("Entrega e pagamento", {"fields": ("endereco_entrega", "forma_pagamento", "valor_frete")}),
        ("Valores", {"fields": ("valor_itens_display", "valor_total_display")}),
        ("Observações", {"fields": ("observacoes",), "classes": ("collapse",)}),
    )
    inlines = [ItemPedidoInline, AvaliacaoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _itens=Count("itens", distinct=True),
            _valor=Sum(SUBTOTAL),
        )

    @admin.display(description="comprador", ordering="comprador__nome")
    def comprador_link(self, obj):
        return link_admin(obj.comprador)

    @admin.display(description="produtor", ordering="produtor__nome")
    def produtor_link(self, obj):
        return link_admin(obj.produtor)

    @admin.display(description="itens", ordering="_itens")
    def qtd_itens(self, obj):
        return obj._itens

    @admin.display(description="valor dos itens")
    def valor_itens_display(self, obj):
        return brl(obj.valor_itens) if obj.pk else "-"

    @admin.display(description="valor total (c/ frete)", ordering="_valor")
    def valor_total_display(self, obj):
        if not obj.pk:
            return "-"
        itens = getattr(obj, "_valor", None)
        if itens is None:
            itens = obj.valor_itens
        return brl(itens + obj.valor_frete)

    @admin.display(description="avaliado?", boolean=True)
    def tem_avaliacao(self, obj):
        return hasattr(obj, "avaliacao")


@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "pedido_link", "lote", "fruta", "quantidade_kg", "preco_unitario", "subtotal_display")
    list_filter = ("lote__cultura__fruta", "pedido__status")
    search_fields = ("pedido__codigo", "lote__codigo", "lote__cultura__variedade")
    ordering = ("-pedido__data_pedido", "id")
    list_per_page = 50
    list_select_related = ("pedido", "lote__cultura")
    autocomplete_fields = ("pedido", "lote")
    readonly_fields = ("subtotal_display",)

    def get_queryset(self, request):
        sub = ExpressionWrapper(F("quantidade_kg") * F("preco_unitario"),
                                output_field=DecimalField(max_digits=14, decimal_places=2))
        return super().get_queryset(request).annotate(_subtotal=sub)

    @admin.display(description="pedido", ordering="pedido__codigo")
    def pedido_link(self, obj):
        return link_admin(obj.pedido, obj.pedido.codigo)

    @admin.display(description="fruta", ordering="lote__cultura__fruta")
    def fruta(self, obj):
        return obj.lote.cultura.get_fruta_display()

    @admin.display(description="subtotal", ordering="_subtotal")
    def subtotal_display(self, obj):
        return brl(obj.subtotal) if obj.pk else "-"


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("pedido_link", "comprador", "produtor", "estrelas", "qualidade_fruta",
                    "pontualidade", "criada_em")
    list_filter = ("nota", "qualidade_fruta", "pontualidade", "criada_em")
    search_fields = ("pedido__codigo", "pedido__comprador__nome", "pedido__produtor__nome", "comentario")
    ordering = ("-criada_em",)
    list_per_page = 30
    list_select_related = ("pedido__comprador", "pedido__produtor")
    autocomplete_fields = ("pedido",)
    readonly_fields = ("criada_em",)
    fieldsets = (
        (None, {"fields": ("pedido", "criada_em")}),
        ("Notas", {"fields": (("nota", "qualidade_fruta", "pontualidade"),)}),
        ("Comentário", {"fields": ("comentario",)}),
    )

    @admin.display(description="pedido", ordering="pedido__codigo")
    def pedido_link(self, obj):
        return link_admin(obj.pedido, obj.pedido.codigo)

    @admin.display(description="comprador", ordering="pedido__comprador__nome")
    def comprador(self, obj):
        return obj.pedido.comprador

    @admin.display(description="produtor", ordering="pedido__produtor__nome")
    def produtor(self, obj):
        return obj.pedido.produtor

    @admin.display(description="nota", ordering="nota")
    def estrelas(self, obj):
        return "★" * obj.nota + "☆" * (5 - obj.nota)


@admin.register(CotacaoCambio)
class CotacaoCambioAdmin(admin.ModelAdmin):
    list_display = ("data", "moeda", "compra", "venda", "spread_display", "fonte")
    list_filter = ("moeda", "fonte", "data")
    search_fields = ("moeda", "fonte")
    ordering = ("-data", "moeda")
    list_per_page = 50
    date_hierarchy = "data"
    readonly_fields = ("spread_display",)
    fieldsets = (
        (None, {"fields": ("moeda", "data", "fonte")}),
        ("Valores", {"fields": (("compra", "venda"), "spread_display")}),
    )

    @admin.display(description="spread")
    def spread_display(self, obj):
        return f"{obj.spread:.4f}" if obj.pk else "-"
