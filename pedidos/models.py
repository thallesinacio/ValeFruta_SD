"""Models da aplicação *pedidos*.

Representa o lado da demanda do ValeFruta: quem compra (Comprador), o que foi
comprado (Pedido e ItemPedido), como foi a experiência (Avaliacao) e a cotação
de moedas usada como referência de preço para exportação (CotacaoCambio).
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from produtores.models import UF_CHOICES, Lote, Produtor, telefone_validator, validar_documento


class Comprador(models.Model):
    """Comprador (feirante, mercado, restaurante, distribuidor ou exportador)."""

    class Tipo(models.TextChoices):
        FEIRANTE = "feirante", "Feirante"
        MERCADO = "mercado", "Mercado / supermercado"
        RESTAURANTE = "restaurante", "Restaurante / lanchonete"
        DISTRIBUIDOR = "distribuidor", "Distribuidor / atacadista"
        INDUSTRIA = "industria", "Indústria de polpas e sucos"
        EXPORTADOR = "exportador", "Exportador"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="comprador", verbose_name="usuário",
    )
    nome = models.CharField("nome / razão social", max_length=150)
    tipo = models.CharField("tipo de comprador", max_length=15, choices=Tipo.choices)
    tipo_pessoa = models.CharField("tipo de pessoa", max_length=2,
                                   choices=Produtor.TipoPessoa.choices,
                                   default=Produtor.TipoPessoa.JURIDICA)
    documento = models.CharField("CPF/CNPJ", max_length=18, unique=True)
    telefone = models.CharField("telefone", max_length=16, validators=[telefone_validator])
    endereco = models.CharField("endereço", max_length=200)
    municipio = models.CharField("município", max_length=60)
    uf = models.CharField("UF", max_length=2, choices=UF_CHOICES)
    data_cadastro = models.DateTimeField("data de cadastro", default=timezone.now)

    class Meta:
        ordering = ["nome"]
        verbose_name = "comprador"
        verbose_name_plural = "compradores"

    def __str__(self):
        return self.nome

    def clean(self):
        validar_documento(self.tipo_pessoa, self.documento)


class PedidoQuerySet(models.QuerySet):
    def com_totais(self):
        """Anota em cada pedido o valor total e a quantidade de itens."""
        subtotal = ExpressionWrapper(
            F("itens__quantidade_kg") * F("itens__preco_unitario"),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
        return self.annotate(total_anotado=Sum(subtotal), qtd_itens=models.Count("itens"))


class Pedido(models.Model):
    """Pedido feito por um comprador a UM produtor (um pedido por vendedor)."""

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ACEITO = "aceito", "Aceito pelo produtor"
        EM_TRANSPORTE = "em_transporte", "Em transporte"
        ENTREGUE = "entregue", "Entregue"
        CANCELADO = "cancelado", "Cancelado"

    class Pagamento(models.TextChoices):
        PIX = "pix", "PIX"
        BOLETO = "boleto", "Boleto"
        TRANSFERENCIA = "transferencia", "Transferência bancária"
        PRAZO_30 = "prazo_30", "A prazo (30 dias)"
        DINHEIRO = "dinheiro", "Dinheiro na entrega"

    codigo = models.CharField("código", max_length=20, unique=True)
    comprador = models.ForeignKey(Comprador, on_delete=models.PROTECT,
                                  related_name="pedidos", verbose_name="comprador")
    produtor = models.ForeignKey(Produtor, on_delete=models.PROTECT,
                                 related_name="pedidos_recebidos", verbose_name="produtor")
    status = models.CharField("status", max_length=15, choices=Status.choices,
                              default=Status.PENDENTE)
    forma_pagamento = models.CharField("forma de pagamento", max_length=15,
                                       choices=Pagamento.choices, default=Pagamento.PIX)
    data_pedido = models.DateTimeField("data do pedido", default=timezone.now)
    data_entrega_prevista = models.DateField("entrega prevista")
    data_entrega = models.DateField("entregue em", null=True, blank=True)
    endereco_entrega = models.CharField("endereço de entrega", max_length=200)
    valor_frete = models.DecimalField("frete (R$)", max_digits=10, decimal_places=2,
                                      default=Decimal("0"),
                                      validators=[MinValueValidator(Decimal("0"))])
    observacoes = models.TextField("observações", blank=True)

    objects = PedidoQuerySet.as_manager()

    class Meta:
        ordering = ["-data_pedido"]
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"

    def __str__(self):
        return f"{self.codigo} · {self.comprador}"

    @property
    def valor_itens(self):
        return sum((item.subtotal for item in self.itens.all()), Decimal("0"))

    @property
    def valor_total(self):
        return self.valor_itens + (self.valor_frete or 0)

    def clean(self):
        erros = {}
        if self.data_pedido and self.data_entrega_prevista:
            if self.data_entrega_prevista < timezone.localtime(self.data_pedido).date():
                erros["data_entrega_prevista"] = "A entrega prevista não pode ser anterior ao pedido."
        if self.status == self.Status.ENTREGUE and not self.data_entrega:
            erros["data_entrega"] = "Informe a data de entrega para pedidos entregues."
        if self.data_entrega and self.status != self.Status.ENTREGUE:
            erros["status"] = "Só pedidos com status 'Entregue' podem ter data de entrega."
        if erros:
            raise ValidationError(erros)


class ItemPedido(models.Model):
    """Item de um pedido: certa quantidade de um lote, ao preço do momento."""

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE,
                               related_name="itens", verbose_name="pedido")
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT,
                             related_name="itens_pedido", verbose_name="lote")
    quantidade_kg = models.DecimalField(
        "quantidade (kg)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("1"))],
    )
    preco_unitario = models.DecimalField(
        "preço por kg (R$)", max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.10"))],
        help_text="Preço do lote no momento da compra.",
    )

    class Meta:
        ordering = ["pedido", "id"]
        verbose_name = "item do pedido"
        verbose_name_plural = "itens do pedido"
        constraints = [
            models.UniqueConstraint(fields=["pedido", "lote"], name="item_lote_unico_por_pedido"),
        ]

    def __str__(self):
        return f"{self.quantidade_kg} kg de {self.lote.cultura}"

    @property
    def subtotal(self):
        return (self.quantidade_kg or 0) * (self.preco_unitario or 0)

    def clean(self):
        if not (self.pedido_id and self.lote_id):
            return
        erros = {}
        if self.lote.propriedade.produtor_id != self.pedido.produtor_id:
            erros["lote"] = "O lote precisa pertencer ao produtor do pedido."
        if self._state.adding and self.quantidade_kg and self.quantidade_kg > self.lote.quantidade_disponivel_kg:
            erros["quantidade_kg"] = (
                f"Quantidade maior que a disponível no lote ({self.lote.quantidade_disponivel_kg} kg)."
            )
        if erros:
            raise ValidationError(erros)


class Avaliacao(models.Model):
    """Avaliação do comprador sobre um pedido entregue (no máximo uma por pedido)."""

    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE,
                                  related_name="avaliacao", verbose_name="pedido")
    nota = models.PositiveSmallIntegerField(
        "nota", validators=[MinValueValidator(1), MaxValueValidator(5)],
        choices=[(n, "★" * n) for n in range(1, 6)],
    )
    qualidade_fruta = models.PositiveSmallIntegerField(
        "qualidade da fruta", validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    pontualidade = models.PositiveSmallIntegerField(
        "pontualidade da entrega", validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comentario = models.TextField("comentário", blank=True)
    criada_em = models.DateTimeField("criada em", default=timezone.now)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "avaliação"
        verbose_name_plural = "avaliações"

    def __str__(self):
        return f"{self.pedido.codigo} · {self.nota}/5"

    def clean(self):
        if self.pedido_id and self.pedido.status != Pedido.Status.ENTREGUE:
            raise ValidationError({"pedido": "Só é possível avaliar pedidos entregues."})


class CotacaoCambio(models.Model):
    """Cotação diária de moeda estrangeira (referência para exportação)."""

    class Moeda(models.TextChoices):
        USD = "USD", "Dólar americano (USD)"
        EUR = "EUR", "Euro (EUR)"

    moeda = models.CharField("moeda", max_length=3, choices=Moeda.choices)
    data = models.DateField("data")
    compra = models.DecimalField("compra (R$)", max_digits=8, decimal_places=4,
                                 validators=[MinValueValidator(Decimal("0.0001"))])
    venda = models.DecimalField("venda (R$)", max_digits=8, decimal_places=4,
                                validators=[MinValueValidator(Decimal("0.0001"))])
    fonte = models.CharField("fonte", max_length=60, default="AwesomeAPI")

    class Meta:
        ordering = ["-data", "moeda"]
        verbose_name = "cotação de câmbio"
        verbose_name_plural = "cotações de câmbio"
        constraints = [
            models.UniqueConstraint(fields=["moeda", "data"], name="cotacao_unica_por_dia"),
        ]

    def __str__(self):
        return f"{self.moeda} {self.data:%d/%m/%Y}: R$ {self.venda}"

    def clean(self):
        if self.compra is not None and self.venda is not None and self.venda < self.compra:
            raise ValidationError({"venda": "O valor de venda não pode ser menor que o de compra."})

    @property
    def spread(self):
        return self.venda - self.compra
