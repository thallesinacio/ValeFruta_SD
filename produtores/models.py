"""Models da aplicação *produtores*.

Representa o lado da oferta do ValeFruta: quem produz (Produtor), onde produz
(Propriedade), o que produz (Cultura), quais selos possui (Certificacao) e o
que está à venda (Lote).
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

# --------------------------------------------------------------------------- #
# Constantes e validadores compartilhados
# --------------------------------------------------------------------------- #

UF_CHOICES = [
    ("PE", "Pernambuco"),
    ("BA", "Bahia"),
    ("PI", "Piauí"),
    ("CE", "Ceará"),
    ("PB", "Paraíba"),
    ("SE", "Sergipe"),
    ("AL", "Alagoas"),
    ("RN", "Rio Grande do Norte"),
]

telefone_validator = RegexValidator(
    regex=r"^\(\d{2}\) \d{4,5}-\d{4}$",
    message="Informe o telefone no formato (87) 99999-9999.",
)
cpf_validator = RegexValidator(
    regex=r"^\d{3}\.\d{3}\.\d{3}-\d{2}$",
    message="Informe o CPF no formato 000.000.000-00.",
)
cnpj_validator = RegexValidator(
    regex=r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$",
    message="Informe o CNPJ no formato 00.000.000/0000-00.",
)


def validar_documento(tipo_pessoa, documento, campo="documento"):
    """Valida CPF (pessoa física) ou CNPJ (pessoa jurídica) conforme o tipo."""
    validador = cpf_validator if tipo_pessoa == "PF" else cnpj_validator
    try:
        validador(documento)
    except ValidationError as erro:
        raise ValidationError({campo: erro.messages})


# --------------------------------------------------------------------------- #
# Tabelas de catálogo
# --------------------------------------------------------------------------- #

class Certificacao(models.Model):
    """Selo ou certificação de boas práticas (ex.: GlobalG.A.P., Orgânico)."""

    sigla = models.CharField("sigla", max_length=30, unique=True)
    nome = models.CharField("nome", max_length=120)
    orgao_emissor = models.CharField("órgão emissor", max_length=120)
    exigida_exportacao = models.BooleanField(
        "exigida para exportação", default=False,
        help_text="Marque se o selo costuma ser exigido por importadores.",
    )
    descricao = models.TextField("descrição", blank=True)

    class Meta:
        ordering = ["sigla"]
        verbose_name = "certificação"
        verbose_name_plural = "certificações"

    def __str__(self):
        return self.sigla


class Cultura(models.Model):
    """Fruta + variedade cultivada no Vale (ex.: Manga Tommy Atkins)."""

    class Fruta(models.TextChoices):
        MANGA = "manga", "Manga"
        UVA = "uva", "Uva"
        GOIABA = "goiaba", "Goiaba"
        ACEROLA = "acerola", "Acerola"
        BANANA = "banana", "Banana"
        COCO = "coco", "Coco"
        MARACUJA = "maracuja", "Maracujá"
        MELAO = "melao", "Melão"
        MELANCIA = "melancia", "Melancia"
        LIMAO = "limao", "Limão"
        MAMAO = "mamao", "Mamão"
        PINHA = "pinha", "Pinha"
        ATEMOIA = "atemoia", "Atemoia"
        GRAVIOLA = "graviola", "Graviola"

    fruta = models.CharField("fruta", max_length=20, choices=Fruta.choices)
    variedade = models.CharField("variedade", max_length=60)
    nome_cientifico = models.CharField("nome científico", max_length=80, blank=True)
    ciclo_dias = models.PositiveSmallIntegerField(
        "ciclo até a colheita (dias)",
        validators=[MinValueValidator(30), MaxValueValidator(730)],
        help_text="Tempo médio entre poda/plantio e colheita.",
    )
    perene = models.BooleanField("cultura perene", default=True)
    descricao = models.TextField("descrição", blank=True)

    class Meta:
        ordering = ["fruta", "variedade"]
        verbose_name = "cultura"
        verbose_name_plural = "culturas"
        constraints = [
            models.UniqueConstraint(fields=["fruta", "variedade"], name="cultura_fruta_variedade_unica"),
        ]

    def __str__(self):
        return f"{self.get_fruta_display()} {self.variedade}"


# --------------------------------------------------------------------------- #
# Produtor e propriedade
# --------------------------------------------------------------------------- #

class Produtor(models.Model):
    """Produtor rural. Cada produtor tem exatamente uma conta de usuário."""

    class TipoPessoa(models.TextChoices):
        FISICA = "PF", "Pessoa física"
        JURIDICA = "PJ", "Pessoa jurídica"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="produtor", verbose_name="usuário",
    )
    nome = models.CharField("nome / razão social", max_length=150)
    tipo_pessoa = models.CharField("tipo de pessoa", max_length=2, choices=TipoPessoa.choices,
                                   default=TipoPessoa.FISICA)
    documento = models.CharField("CPF/CNPJ", max_length=18, unique=True)
    telefone = models.CharField("telefone", max_length=16, validators=[telefone_validator])
    municipio = models.CharField("município", max_length=60)
    uf = models.CharField("UF", max_length=2, choices=UF_CHOICES)
    bio = models.TextField("apresentação", blank=True)
    ativo = models.BooleanField("ativo", default=True)
    data_cadastro = models.DateTimeField("data de cadastro", default=timezone.now)

    class Meta:
        ordering = ["nome"]
        verbose_name = "produtor"
        verbose_name_plural = "produtores"

    def __str__(self):
        return self.nome

    def clean(self):
        validar_documento(self.tipo_pessoa, self.documento)


class Propriedade(models.Model):
    """Fazenda, sítio ou lote irrigado pertencente a um produtor."""

    class Irrigacao(models.TextChoices):
        GOTEJAMENTO = "gotejamento", "Gotejamento"
        MICROASPERSAO = "microaspersao", "Microaspersão"
        ASPERSAO = "aspersao", "Aspersão"
        SULCO = "sulco", "Sulco"
        SEQUEIRO = "sequeiro", "Sequeiro (sem irrigação)"

    produtor = models.ForeignKey(
        Produtor, on_delete=models.CASCADE,
        related_name="propriedades", verbose_name="produtor",
    )
    nome = models.CharField("nome", max_length=120)
    municipio = models.CharField("município", max_length=60)
    uf = models.CharField("UF", max_length=2, choices=UF_CHOICES)
    perimetro_irrigado = models.CharField(
        "perímetro irrigado", max_length=80, blank=True,
        help_text="Ex.: Projeto Senador Nilo Coelho, Projeto Maniçoba.",
    )
    area_hectares = models.DecimalField(
        "área (ha)", max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.5")), MaxValueValidator(Decimal("5000"))],
    )
    tipo_irrigacao = models.CharField("tipo de irrigação", max_length=20,
                                      choices=Irrigacao.choices, default=Irrigacao.GOTEJAMENTO)
    latitude = models.DecimalField(
        "latitude", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(Decimal("-12")), MaxValueValidator(Decimal("-7"))],
    )
    longitude = models.DecimalField(
        "longitude", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(Decimal("-43")), MaxValueValidator(Decimal("-38"))],
    )
    culturas = models.ManyToManyField(Cultura, related_name="propriedades",
                                      verbose_name="culturas cultivadas")
    certificacoes = models.ManyToManyField(Certificacao, related_name="propriedades",
                                           blank=True, verbose_name="certificações")

    class Meta:
        ordering = ["produtor__nome", "nome"]
        verbose_name = "propriedade"
        verbose_name_plural = "propriedades"
        constraints = [
            models.UniqueConstraint(fields=["produtor", "nome"], name="propriedade_nome_unico_por_produtor"),
        ]

    def __str__(self):
        return f"{self.nome} ({self.municipio}-{self.uf})"


# --------------------------------------------------------------------------- #
# Lote (oferta)
# --------------------------------------------------------------------------- #

class Lote(models.Model):
    """Lote de frutas colhido em uma propriedade e anunciado na vitrine."""

    class Classificacao(models.TextChoices):
        EXTRA = "extra", "Extra"
        CAT1 = "cat1", "Categoria I"
        CAT2 = "cat2", "Categoria II"
        INDUSTRIA = "industria", "Indústria / polpa"

    class Destino(models.TextChoices):
        INTERNO = "interno", "Mercado interno"
        EXPORTACAO = "exportacao", "Exportação"

    class Status(models.TextChoices):
        DISPONIVEL = "disponivel", "Disponível"
        RESERVADO = "reservado", "Reservado"
        ESGOTADO = "esgotado", "Esgotado"
        CANCELADO = "cancelado", "Cancelado"

    codigo = models.CharField("código", max_length=20, unique=True,
                              help_text="Identificador de rastreabilidade do lote.")
    propriedade = models.ForeignKey(Propriedade, on_delete=models.CASCADE,
                                    related_name="lotes", verbose_name="propriedade")
    cultura = models.ForeignKey(Cultura, on_delete=models.PROTECT,
                                related_name="lotes", verbose_name="cultura")
    classificacao = models.CharField("classificação", max_length=10,
                                     choices=Classificacao.choices, default=Classificacao.CAT1)
    destino = models.CharField("destino", max_length=10, choices=Destino.choices,
                               default=Destino.INTERNO)
    quantidade_kg = models.DecimalField(
        "quantidade colhida (kg)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("10"))],
    )
    quantidade_disponivel_kg = models.DecimalField(
        "quantidade disponível (kg)", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    preco_kg = models.DecimalField(
        "preço por kg (R$)", max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.10")), MaxValueValidator(Decimal("100"))],
    )
    data_colheita = models.DateField("data de colheita")
    validade_dias = models.PositiveSmallIntegerField(
        "validade (dias após colheita)", default=15,
        validators=[MinValueValidator(1), MaxValueValidator(120)],
    )
    status = models.CharField("status", max_length=12, choices=Status.choices,
                              default=Status.DISPONIVEL)
    observacoes = models.TextField("observações", blank=True)
    criado_em = models.DateTimeField("publicado em", default=timezone.now)

    class Meta:
        ordering = ["-data_colheita", "codigo"]
        verbose_name = "lote"
        verbose_name_plural = "lotes"
        # A regra "disponível <= colhido" é validada em clean() para manter o
        # projeto compatível com o Django 3.2 da VM da disciplina e com o 5.x.

    def __str__(self):
        return f"{self.codigo} · {self.cultura}"

    @property
    def valor_estoque(self):
        return (self.quantidade_disponivel_kg or 0) * (self.preco_kg or 0)

    def clean(self):
        erros = {}
        if self.quantidade_kg is not None and self.quantidade_disponivel_kg is not None:
            if self.quantidade_disponivel_kg > self.quantidade_kg:
                erros["quantidade_disponivel_kg"] = "A quantidade disponível não pode ser maior que a colhida."
        if self.data_colheita and self.data_colheita > timezone.localdate():
            erros["data_colheita"] = "A data de colheita não pode estar no futuro."
        if self.propriedade_id and self.cultura_id:
            if not self.propriedade.culturas.filter(pk=self.cultura_id).exists():
                erros["cultura"] = "Esta cultura não está cadastrada na propriedade selecionada."
        if erros:
            raise ValidationError(erros)
