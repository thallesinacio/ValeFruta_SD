"""Popula o banco do ValeFruta com centenas de registros fictícios e coerentes.

Uso:
    python manage.py popular_banco            # popula um banco vazio
    python manage.py popular_banco --limpar   # apaga os dados fictícios e recria

Os dados usam Faker (pt_BR) com semente fixa, então rodar o comando duas vezes
com --limpar gera exatamente o mesmo conteúdo. As datas são calculadas a partir
de uma data de referência fixa (DATA_REFERENCIA) pelo mesmo motivo.
"""

import random
import unicodedata
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone
from faker import Faker

from pedidos.models import Avaliacao, Comprador, CotacaoCambio, ItemPedido, Pedido
from produtores.models import Certificacao, Cultura, Lote, Produtor, Propriedade

SEED = 2026
DATA_REFERENCIA = date(2026, 9, 30)
SENHA_USUARIOS_FAKE = "senha123"
ADMIN_USUARIO = "admin"
ADMIN_SENHA = "admin123"
ADMIN_EMAIL = "admin@valefruta.local"

QTD_PRODUTORES = 250
QTD_PROPRIEDADES = 420
QTD_COMPRADORES = 300
QTD_LOTES = 1500
QTD_PEDIDOS = 1200
INICIO_COTACOES = date(2024, 10, 1)

# --------------------------------------------------------------------------- #
# Dados de domínio
# --------------------------------------------------------------------------- #

# município: (UF, DDD, latitude, longitude, peso, perímetros irrigados)
MUNICIPIOS_VALE = {
    "Petrolina": ("PE", "87", -9.389, -40.503, 30,
                  ["Projeto Senador Nilo Coelho", "Projeto Bebedouro", "Projeto Pontal"]),
    "Juazeiro": ("BA", "74", -9.416, -40.503, 25,
                 ["Projeto Maniçoba", "Projeto Mandacaru", "Projeto Tourão", "Projeto Salitre"]),
    "Lagoa Grande": ("PE", "87", -8.997, -40.272, 8, []),
    "Santa Maria da Boa Vista": ("PE", "87", -8.798, -39.825, 6, ["Projeto Fulgêncio"]),
    "Casa Nova": ("BA", "74", -9.162, -40.971, 8, ["Projeto Senador Nilo Coelho"]),
    "Sobradinho": ("BA", "74", -9.455, -40.823, 4, []),
    "Curaçá": ("BA", "74", -8.990, -39.904, 6, ["Projeto Curaçá"]),
    "Sento Sé": ("BA", "74", -9.741, -41.878, 3, []),
    "Orocó": ("PE", "87", -8.610, -39.601, 3, ["Projeto Brígida"]),
    "Cabrobó": ("PE", "87", -8.514, -39.310, 3, []),
    "Belém do São Francisco": ("PE", "87", -8.754, -38.966, 2, ["Projeto Icó-Mandantes"]),
    "Afrânio": ("PE", "87", -8.515, -41.005, 1, []),
    "Dormentes": ("PE", "87", -8.447, -40.771, 1, []),
}

# Cidades de destino dos compradores de fora do Vale: município → (UF, DDD)
MUNICIPIOS_COMPRADORES_EXTERNOS = {
    "Recife": ("PE", "81"), "Caruaru": ("PE", "81"), "Salgueiro": ("PE", "87"),
    "Serra Talhada": ("PE", "87"), "Salvador": ("BA", "71"), "Feira de Santana": ("BA", "75"),
    "Senhor do Bonfim": ("BA", "74"), "Fortaleza": ("CE", "85"), "Juazeiro do Norte": ("CE", "88"),
    "Teresina": ("PI", "86"), "Picos": ("PI", "89"), "Aracaju": ("SE", "79"),
    "Maceió": ("AL", "82"), "João Pessoa": ("PB", "83"), "Campina Grande": ("PB", "83"),
    "Natal": ("RN", "84"), "Mossoró": ("RN", "84"),
}

# fruta: (nome científico, ciclo, perene, faixa de preço R$/kg, faixa de kg por lote,
#         validade em dias, peso na região, frutas exportáveis?, variedades)
CULTURAS = {
    "manga": ("Mangifera indica", 120, True, (1.20, 4.50), (800, 30000), 20, 40, True,
              ["Tommy Atkins", "Palmer", "Kent", "Keitt", "Haden", "Espada", "Rosa", "Ataulfo"]),
    "uva": ("Vitis spp.", 120, True, (4.00, 14.00), (300, 15000), 30, 35, True,
            ["Vitória", "Arra 15", "BRS Isis", "Sugar Crisp", "Thompson Seedless", "Crimson Seedless",
             "Itália", "Red Globe", "Benitaka", "BRS Magna", "Syrah", "Cabernet Sauvignon"]),
    "goiaba": ("Psidium guajava", 180, True, (1.50, 4.00), (200, 6000), 7, 8, False,
               ["Paluma", "Pedro Sato", "Século XXI"]),
    "acerola": ("Malpighia emarginata", 90, True, (2.00, 6.00), (100, 3000), 4, 6, False,
                ["Junko", "BRS 366 Jaburu", "Flor Branca"]),
    "banana": ("Musa spp.", 365, True, (1.50, 4.00), (300, 8000), 10, 6, False,
               ["Prata Anã", "Pacovan", "Grande Naine"]),
    "coco": ("Cocos nucifera", 365, True, (0.80, 2.00), (500, 10000), 20, 5, False, ["Anão Verde"]),
    "maracuja": ("Passiflora edulis", 240, True, (3.00, 7.00), (200, 4000), 10, 4, False,
                 ["BRS Gigante Amarelo"]),
    "melao": ("Cucumis melo", 70, False, (1.50, 4.00), (1000, 20000), 25, 5, True,
              ["Amarelo", "Pele de Sapo", "Cantaloupe"]),
    "melancia": ("Citrullus lanatus", 80, False, (0.80, 2.20), (2000, 25000), 20, 4, False,
                 ["Crimson Sweet", "Fairfax"]),
    "limao": ("Citrus latifolia", 180, True, (2.00, 6.00), (300, 8000), 20, 4, True, ["Tahiti"]),
    "mamao": ("Carica papaya", 270, True, (1.50, 4.50), (300, 8000), 8, 4, True, ["Formosa", "Havaí"]),
    "pinha": ("Annona squamosa", 150, True, (6.00, 14.00), (100, 2000), 5, 3, False, ["Comum"]),
    "atemoia": ("Annona × atemoya", 180, True, (8.00, 16.00), (100, 2000), 7, 2, False, ["Gefner"]),
    "graviola": ("Annona muricata", 180, True, (6.00, 12.00), (100, 1500), 5, 2, False, ["Morada"]),
}

CERTIFICACOES = [
    ("GLOBALG.A.P.", "Global Good Agricultural Practice", "FoodPLUS GmbH", True,
     "Padrão internacional de boas práticas agrícolas exigido pela maioria dos importadores europeus."),
    ("PIF", "Produção Integrada de Frutas", "MAPA / Inmetro", True,
     "Sistema brasileiro de produção integrada com rastreabilidade e uso racional de defensivos."),
    ("ORGÂNICO BR", "Produto Orgânico Brasil", "MAPA / SisOrg", False,
     "Selo federal do Sistema Brasileiro de Avaliação da Conformidade Orgânica."),
    ("RAINFOREST", "Rainforest Alliance", "Rainforest Alliance", True,
     "Certificação de sustentabilidade social e ambiental."),
    ("FAIRTRADE", "Comércio Justo", "Fairtrade International", True,
     "Garante preço mínimo e prêmio social a pequenos produtores organizados."),
    ("BRCGS", "BRCGS Food Safety", "BRCGS", True, "Segurança de alimentos em packing houses."),
    ("SMETA", "Sedex Members Ethical Trade Audit", "Sedex", True, "Auditoria de práticas trabalhistas e éticas."),
    ("LEAF", "LEAF Marque", "Linking Environment And Farming", True,
     "Certificação ambiental exigida por redes varejistas do Reino Unido."),
    ("IG VSSF", "Indicação Geográfica Vale do Submédio São Francisco", "INPI", False,
     "Indicação de procedência para uvas de mesa e mangas produzidas no Submédio São Francisco."),
]

COMENTARIOS = {
    5: ["Frutas excelentes, padrão de exportação. Recomendo!", "Entrega no horário e calibre uniforme.",
        "Manga com ótimo brix, clientes elogiaram muito.", "Uva crocante e bem embalada, nota máxima.",
        "Produtor muito atencioso, já fiz o segundo pedido.", "Qualidade impecável, nenhuma caixa com avaria."],
    4: ["Boa qualidade, só atrasou algumas horas.", "Frutas boas, algumas um pouco verdes.",
        "Bom custo-benefício, voltarei a comprar.", "Calibre um pouco desigual, mas sabor muito bom.",
        "Atendimento rápido pelo WhatsApp, recomendo."],
    3: ["Qualidade razoável, esperava mais pelo preço.", "Parte do lote chegou madura demais.",
        "Entrega atrasou um dia, frutas ok.", "Embalagem poderia ser melhor, algumas amassadas."],
    2: ["Muitas frutas com manchas, tive que descartar parte.", "Atraso grande na entrega.",
        "Quantidade entregue menor que a combinada."],
    1: ["Lote chegou fora do padrão anunciado.", "Não recomendo, frutas passadas e sem resposta do produtor."],
}

BIOS = [
    "Produzimos {fruta} irrigada no {local} há {anos} anos, com foco em qualidade e rastreabilidade.",
    "Agricultura familiar no {local}. Trabalhamos com {fruta} e colheita sob encomenda.",
    "Fazenda com packing house própria, atendendo mercado interno e exportação de {fruta}.",
    "Somos produtores de {fruta} no {local}, com entrega para toda a região do Vale.",
    "Produção de {fruta} com manejo integrado de pragas e assistência técnica permanente.",
]

OBS_LOTE = [
    "", "", "", "Embalado em caixas de 4 kg.", "Embalado em caixas de 6 kg.", "Colheita sob encomenda.",
    "Frutas com brix acima de 14.", "Retirada no packing ou entrega combinada.",
    "Lote rastreado com caderno de campo.", "Paletizado, pronto para câmara fria.",
]

TIPOS_COMPRADOR = [  # tipo, peso, faixa de kg por item, chance de ser de fora do Vale
    ("feirante", 30, (20, 300), 0.10),
    ("restaurante", 18, (10, 150), 0.25),
    ("mercado", 22, (100, 2000), 0.45),
    ("distribuidor", 15, (500, 8000), 0.55),
    ("industria", 7, (500, 10000), 0.50),
    ("exportador", 8, (2000, 20000), 0.30),
]

DUAS_CASAS = Decimal("0.01")


def dec(valor, casas=DUAS_CASAS):
    return Decimal(str(valor)).quantize(casas, rounding=ROUND_HALF_UP)


def slug(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in texto.lower() if c.isalnum() or c == " ").split()


class Command(BaseCommand):
    help = "Popula o banco do ValeFruta com centenas de registros fictícios (Faker pt_BR, seed fixa)."

    def add_arguments(self, parser):
        parser.add_argument("--limpar", action="store_true",
                            help="Apaga os dados fictícios existentes antes de popular de novo.")

    # ------------------------------------------------------------------ #
    def handle(self, *args, **opcoes):
        if opcoes["limpar"]:
            self.limpar()
        elif Produtor.objects.exists() or Comprador.objects.exists():
            raise CommandError("O banco já tem dados. Use --limpar para apagar e popular de novo.")

        self.rng = random.Random(SEED)
        Faker.seed(SEED)
        self.fake = Faker("pt_BR")
        self.fake.seed_instance(SEED)
        self.senha_hash = make_password(SENHA_USUARIOS_FAKE)
        self.usernames = set()
        self.tz = timezone.get_current_timezone()

        with transaction.atomic():
            self.criar_admin()
            self.criar_certificacoes()
            self.criar_culturas()
            self.criar_produtores()
            self.criar_propriedades()
            self.criar_compradores()
            self.criar_lotes()
            self.criar_pedidos()
            self.criar_avaliacoes()
            self.criar_cotacoes()

        self.imprimir_resumo()

    # ------------------------------------------------------------------ #
    def limpar(self):
        self.stdout.write("Apagando dados fictícios...")
        with transaction.atomic():
            Avaliacao.objects.all().delete()
            ItemPedido.objects.all().delete()
            Pedido.objects.all().delete()
            CotacaoCambio.objects.all().delete()
            Comprador.objects.all().delete()
            Lote.objects.all().delete()
            Propriedade.objects.all().delete()
            Produtor.objects.all().delete()
            Cultura.objects.all().delete()
            Certificacao.objects.all().delete()
            get_user_model().objects.filter(is_superuser=False, is_staff=False).delete()
            if connection.vendor == "sqlite":
                # Zera os contadores de ID para que a recriação gere os mesmos IDs.
                tabelas = [m._meta.db_table for m in (Avaliacao, ItemPedido, Pedido, CotacaoCambio, Comprador,
                                                      Lote, Propriedade, Produtor, Cultura, Certificacao)]
                tabelas += [Propriedade.culturas.through._meta.db_table,
                            Propriedade.certificacoes.through._meta.db_table,
                            get_user_model()._meta.db_table]
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM sqlite_sequence WHERE name IN ({','.join(['%s'] * len(tabelas))})", tabelas
                    )

    # ------------------------------------------------------------------ #
    # Utilitários
    # ------------------------------------------------------------------ #
    def bulk(self, model, objs):
        """bulk_create que garante os IDs preenchidos em qualquer versão do Django.

        No Django 3.2 + SQLite (ambiente da VM da disciplina) o bulk_create não
        devolve as chaves primárias; nesse caso elas são lidas de volta do banco,
        na mesma ordem em que os registros foram inseridos.
        """
        ultimo = model.objects.aggregate(m=Max("pk"))["m"] or 0
        model.objects.bulk_create(objs, batch_size=500)
        if objs and objs[0].pk is None:
            pks = list(model.objects.filter(pk__gt=ultimo).order_by("pk").values_list("pk", flat=True))
            if len(pks) != len(objs):
                raise CommandError(f"Não foi possível recuperar os IDs de {model.__name__}.")
            for obj, pk in zip(objs, pks):
                obj.pk = pk
                obj._state.adding = False
                obj._state.db = "default"
        return objs

    def momento(self, dia, hora_min=6, hora_max=20):
        hora = time(self.rng.randint(hora_min, hora_max), self.rng.randint(0, 59), self.rng.randint(0, 59))
        return timezone.make_aware(datetime.combine(dia, hora), self.tz)

    def telefone(self, ddd):
        return f"({ddd}) 9{self.rng.randint(8000, 9999)}-{self.rng.randint(0, 9999):04d}"

    def municipio_vale(self):
        nomes = list(MUNICIPIOS_VALE)
        return self.rng.choices(nomes, weights=[MUNICIPIOS_VALE[n][4] for n in nomes])[0]

    def novo_usuario(self, nome, data_cadastro):
        User = get_user_model()
        partes = slug(nome) or ["usuario"]
        base = f"{partes[0]}.{partes[-1]}" if len(partes) > 1 else partes[0]
        username, n = base[:140], 1
        while username in self.usernames:
            n += 1
            username = f"{base[:140]}{n}"
        self.usernames.add(username)
        primeiro = nome.split()[0]
        return User(
            username=username, email=f"{username}@{self.fake.free_email_domain()}",
            first_name=primeiro[:150], last_name=" ".join(nome.split()[1:])[:150],
            password=self.senha_hash, is_active=True, date_joined=data_cadastro,
        )

    # ------------------------------------------------------------------ #
    # Criação dos dados, em ordem de dependência
    # ------------------------------------------------------------------ #
    def criar_admin(self):
        User = get_user_model()
        admin, _ = User.objects.get_or_create(username=ADMIN_USUARIO,
                                              defaults={"email": ADMIN_EMAIL, "first_name": "Administrador"})
        admin.is_staff = admin.is_superuser = admin.is_active = True
        admin.set_password(ADMIN_SENHA)
        admin.save()
        self.usernames.add(ADMIN_USUARIO)

    def criar_certificacoes(self):
        self.certificacoes = self.bulk(Certificacao, [
            Certificacao(sigla=s, nome=n, orgao_emissor=o, exigida_exportacao=e, descricao=d)
            for s, n, o, e, d in CERTIFICACOES
        ])

    def criar_culturas(self):
        objs, self.info_cultura = [], {}
        for fruta, (cientifico, ciclo, perene, *_resto, variedades) in CULTURAS.items():
            for variedade in variedades:
                objs.append(Cultura(
                    fruta=fruta, variedade=variedade, nome_cientifico=cientifico,
                    ciclo_dias=ciclo, perene=perene,
                    descricao=f"{Cultura.Fruta(fruta).label} da variedade {variedade}, "
                              f"cultivada sob irrigação no Submédio São Francisco.",
                ))
        self.culturas = self.bulk(Cultura, objs)
        self.culturas_por_fruta = defaultdict(list)
        for c in self.culturas:
            self.culturas_por_fruta[c.fruta].append(c)

    def criar_produtores(self):
        usuarios, dados = [], []
        inicio = DATA_REFERENCIA - timedelta(days=3 * 365)
        for _ in range(QTD_PRODUTORES):
            pj = self.rng.random() < 0.25
            sobrenome = self.fake.last_name()
            if pj:
                nome = self.rng.choice([
                    f"Agrícola {sobrenome} Ltda", f"{sobrenome} Frutas do Vale Ltda",
                    f"Fazenda {sobrenome} Agropecuária", f"Agropecuária {sobrenome} & Filhos",
                    f"{sobrenome} Fruticultura Ltda", f"Vale {sobrenome} Agronegócios",
                ])
                documento = self.fake.unique.cnpj()
            else:
                nome = self.fake.name()
                documento = self.fake.unique.cpf()
            municipio = self.municipio_vale()
            uf, ddd, *_ = MUNICIPIOS_VALE[municipio]
            cadastro = self.momento(self.fake.date_between(inicio, DATA_REFERENCIA - timedelta(days=200)))
            usuarios.append(self.novo_usuario(nome, cadastro))
            fruta = self.rng.choice(["manga", "uva", "manga e uva", "goiaba e acerola", "frutas tropicais"])
            bio = self.rng.choice(BIOS).format(fruta=fruta, local=f"Vale do São Francisco ({municipio})",
                                               anos=self.rng.randint(3, 35))
            dados.append(dict(nome=nome, tipo_pessoa="PJ" if pj else "PF", documento=documento,
                              telefone=self.telefone(ddd), municipio=municipio, uf=uf, bio=bio,
                              ativo=self.rng.random() > 0.06, data_cadastro=cadastro))
        usuarios = self.bulk(get_user_model(), usuarios)
        self.produtores = self.bulk(Produtor,
            [Produtor(usuario=u, **d) for u, d in zip(usuarios, dados)]
        )

    def criar_propriedades(self):
        frutas = list(CULTURAS)
        pesos_fruta = [CULTURAS[f][6] for f in frutas]
        donos = list(self.produtores) + self.rng.choices(self.produtores, k=QTD_PROPRIEDADES - QTD_PRODUTORES)
        objs, nomes_usados = [], defaultdict(set)
        self.culturas_da_prop, self.certs_da_prop = [], []
        for produtor in donos:
            municipio = produtor.municipio if self.rng.random() < 0.7 else self.municipio_vale()
            uf, _ddd, lat, lon, _peso, perimetros = MUNICIPIOS_VALE[municipio]
            perimetro = self.rng.choice(perimetros) if perimetros and self.rng.random() < 0.65 else ""
            if perimetro and self.rng.random() < 0.5:
                nome = f"Lote {self.rng.randint(1, 450)} - Núcleo N{self.rng.randint(1, 11)}"
            else:
                nome = self.rng.choice(["Fazenda", "Fazenda", "Sítio", "Chácara", "Agrícola"]) + " " + \
                    self.rng.choice([self.fake.last_name(), "Boa Vista", "Santa Luzia", "São José", "Bom Jesus",
                                     "Nova Esperança", "Água Viva", "Riacho Seco", "Massangano", "Ilha do Rodeadouro",
                                     "Vale Verde", "Pau Ferro", "Carnaíba", "Umbuzeiro", "Juremal"])
            base, n = nome, 1
            while nome in nomes_usados[produtor.pk]:
                n += 1
                nome = f"{base} {n}"
            nomes_usados[produtor.pk].add(nome)

            if produtor.tipo_pessoa == "PJ":
                area = self.rng.uniform(30, 900)
            else:
                area = min(self.rng.lognormvariate(2.4, 0.8), 150)
            area = max(area, 1.0)
            n_culturas = self.rng.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
            escolhidas = []  # lista (e não set) para manter a ordem reproduzível
            while len(escolhidas) < n_culturas:
                fruta = self.rng.choices(frutas, weights=pesos_fruta)[0]
                cultura = self.rng.choice(self.culturas_por_fruta[fruta])
                if cultura not in escolhidas:
                    escolhidas.append(cultura)
            frutas_prop = {c.fruta for c in escolhidas}
            if frutas_prop & {"uva", "melao", "melancia"}:
                irrigacao = self.rng.choices(["gotejamento", "microaspersao", "sulco"], weights=[75, 15, 10])[0]
            else:
                irrigacao = self.rng.choices(["microaspersao", "gotejamento", "aspersao", "sulco", "sequeiro"],
                                             weights=[50, 30, 10, 7, 3])[0]

            chance_cert = 0.75 if produtor.tipo_pessoa == "PJ" else 0.25
            certs = []
            if self.rng.random() < chance_cert:
                certs = self.rng.sample(self.certificacoes, self.rng.choices([1, 2, 3], weights=[50, 35, 15])[0])

            objs.append(Propriedade(
                produtor=produtor, nome=nome, municipio=municipio, uf=uf, perimetro_irrigado=perimetro,
                area_hectares=dec(area), tipo_irrigacao=irrigacao,
                latitude=dec(lat + self.rng.uniform(-0.12, 0.12), Decimal("0.000001")),
                longitude=dec(lon + self.rng.uniform(-0.12, 0.12), Decimal("0.000001")),
            ))
            self.culturas_da_prop.append(escolhidas)
            self.certs_da_prop.append(certs)

        self.propriedades = self.bulk(Propriedade, objs)
        ThroughCultura = Propriedade.culturas.through
        ThroughCert = Propriedade.certificacoes.through
        ThroughCultura.objects.bulk_create([
            ThroughCultura(propriedade_id=p.pk, cultura_id=c.pk)
            for p, cs in zip(self.propriedades, self.culturas_da_prop) for c in cs
        ])
        ThroughCert.objects.bulk_create([
            ThroughCert(propriedade_id=p.pk, certificacao_id=c.pk)
            for p, cs in zip(self.propriedades, self.certs_da_prop) for c in cs
        ])

    def criar_compradores(self):
        usuarios, dados = [], []
        self.faixa_kg_comprador = {}
        inicio = DATA_REFERENCIA - timedelta(days=3 * 365)
        tipos = [t[0] for t in TIPOS_COMPRADOR]
        pesos = [t[1] for t in TIPOS_COMPRADOR]
        info = {t[0]: t for t in TIPOS_COMPRADOR}
        for _ in range(QTD_COMPRADORES):
            tipo = self.rng.choices(tipos, weights=pesos)[0]
            sobrenome, primeiro = self.fake.last_name(), self.fake.first_name()
            pj = tipo != "feirante" or self.rng.random() < 0.15
            if tipo == "feirante":
                nome = self.fake.name() if not pj else f"Hortifruti {primeiro}"
            elif tipo == "restaurante":
                nome = self.rng.choice([f"Restaurante {sobrenome}", f"Bodega do {primeiro}",
                                        f"Churrascaria {sobrenome}", f"Sabor do Velho Chico {sobrenome}",
                                        f"Lanchonete {primeiro}", f"Sorveteria {sobrenome}"])
            elif tipo == "mercado":
                nome = self.rng.choice([f"Supermercado {sobrenome}", f"Mercadinho {primeiro}",
                                        f"Mercado Bom Preço {sobrenome}", f"Hortifruti {sobrenome}"])
            elif tipo == "distribuidor":
                nome = self.rng.choice([f"{sobrenome} Distribuidora de Frutas Ltda", f"Ceasa Box {sobrenome}",
                                        f"Atacado de Frutas {sobrenome}", f"{sobrenome} Hortifrutigranjeiros"])
            elif tipo == "industria":
                nome = self.rng.choice([f"Polpas {sobrenome} Ltda", f"{sobrenome} Sucos e Polpas",
                                        f"Doces {sobrenome} Indústria", f"Vale Polpas {sobrenome}"])
            else:
                nome = self.rng.choice([f"{sobrenome} Export Ltda", f"Vale {sobrenome} Exportadora",
                                        f"{sobrenome} Fruit Trading", f"São Francisco {sobrenome} Exportação"])
            if self.rng.random() < info[tipo][3]:
                municipio = self.rng.choice(list(MUNICIPIOS_COMPRADORES_EXTERNOS))
                uf, ddd = MUNICIPIOS_COMPRADORES_EXTERNOS[municipio]
            else:
                municipio = self.rng.choice(["Petrolina", "Juazeiro", "Petrolina", "Juazeiro",
                                             "Lagoa Grande", "Casa Nova", "Sobradinho"])
                uf, ddd = MUNICIPIOS_VALE[municipio][0], MUNICIPIOS_VALE[municipio][1]
            endereco = f"{self.fake.street_name()}, {self.fake.building_number()} - {self.fake.bairro()}"
            cadastro = self.momento(self.fake.date_between(inicio, DATA_REFERENCIA - timedelta(days=90)))
            usuarios.append(self.novo_usuario(nome, cadastro))
            dados.append(dict(
                nome=nome, tipo=tipo, tipo_pessoa="PJ" if pj else "PF",
                documento=self.fake.unique.cnpj() if pj else self.fake.unique.cpf(),
                telefone=self.telefone(ddd), endereco=endereco, municipio=municipio, uf=uf,
                data_cadastro=cadastro,
            ))
        usuarios = self.bulk(get_user_model(), usuarios)
        self.compradores = self.bulk(Comprador,
            [Comprador(usuario=u, **d) for u, d in zip(usuarios, dados)]
        )
        for c in self.compradores:
            self.faixa_kg_comprador[c.pk] = info[c.tipo][2]

    def criar_lotes(self):
        certs_export = {c.pk for c in self.certificacoes if c.exigida_exportacao}
        props = list(zip(self.propriedades, self.culturas_da_prop, self.certs_da_prop))
        pesos = [float(p.area_hectares) ** 0.5 for p, *_ in props]
        objs = []
        for seq in range(1, QTD_LOTES + 1):
            prop, culturas, certs = self.rng.choices(props, weights=pesos)[0]
            cultura = self.rng.choice(culturas)
            (_c, _ciclo, _p, (pmin, pmax), (kmin, kmax), validade, _peso, exportavel, _v) = CULTURAS[cultura.fruta]
            colheita = DATA_REFERENCIA - timedelta(days=int(self.rng.triangular(0, 365, 20)))
            classificacao = self.rng.choices(["extra", "cat1", "cat2", "industria"], weights=[20, 45, 25, 10])[0]
            pode_exportar = exportavel and classificacao in ("extra", "cat1") and \
                bool(certs_export & {c.pk for c in certs})
            destino = "exportacao" if pode_exportar and self.rng.random() < 0.6 else "interno"
            preco = self.rng.uniform(pmin, pmax)
            preco *= {"extra": 1.15, "cat1": 1.0, "cat2": 0.8, "industria": 0.5}[classificacao]
            if destino == "exportacao":
                preco *= 1.25
            fator_area = min(1.0, float(prop.area_hectares) / 40) * 0.8 + 0.2
            quantidade = max(10.0, self.rng.uniform(kmin, kmax) * fator_area)
            quantidade = round(quantidade / 10) * 10 or 10
            objs.append(Lote(
                codigo=f"VF{colheita:%y}-{seq:05d}", propriedade=prop, cultura=cultura,
                classificacao=classificacao, destino=destino, quantidade_kg=dec(quantidade),
                quantidade_disponivel_kg=dec(quantidade), preco_kg=dec(max(preco, 0.30)),
                data_colheita=colheita, validade_dias=validade, status="disponivel",
                observacoes=self.rng.choice(OBS_LOTE),
                criado_em=self.momento(colheita, 7, 18),
            ))
        # Lotes ficam em memória até os pedidos definirem o estoque restante.
        self.lotes = objs

    def criar_pedidos(self):
        lotes_por_produtor = defaultdict(list)
        for lote in self.lotes:
            lotes_por_produtor[lote.propriedade.produtor_id].append(lote)
        produtores = {p.pk: p for p in self.produtores}
        restante = {id(l): l.quantidade_kg for l in self.lotes}
        cancelado_lote = {id(l) for l in self.lotes if self.rng.random() < 0.02}

        pedidos, itens_por_pedido = [], []
        tentativas = 0
        while len(pedidos) < QTD_PEDIDOS and tentativas < QTD_PEDIDOS * 20:
            tentativas += 1
            ancora = self.rng.choice(self.lotes)
            if id(ancora) in cancelado_lote or restante[id(ancora)] < 1:
                continue
            dia = min(ancora.data_colheita + timedelta(days=self.rng.randint(0, 10)), DATA_REFERENCIA)
            comprador = self.rng.choice(self.compradores)
            produtor_id = ancora.propriedade.produtor_id
            candidatos = [l for l in lotes_por_produtor[produtor_id]
                          if l is not ancora and id(l) not in cancelado_lote and restante[id(l)] >= 1
                          and timedelta(0) <= dia - l.data_colheita <= timedelta(days=25)]
            escolhidos = [ancora] + self.rng.sample(candidatos, min(len(candidatos), self.rng.randint(0, 3)))
            if comprador.tipo == "industria":
                escolhidos = sorted(escolhidos, key=lambda l: l.classificacao != "industria")
            if comprador.tipo == "exportador":
                escolhidos = [l for l in escolhidos if l.destino == "exportacao"] or escolhidos

            idade = (DATA_REFERENCIA - dia).days
            if idade > 15:
                status = self.rng.choices(["entregue", "cancelado"], weights=[90, 10])[0]
            elif idade > 5:
                status = self.rng.choices(["entregue", "em_transporte", "aceito", "cancelado"],
                                          weights=[55, 20, 15, 10])[0]
            else:
                status = self.rng.choices(["pendente", "aceito", "em_transporte", "cancelado"],
                                          weights=[40, 35, 17, 8])[0]

            kmin, kmax = self.faixa_kg_comprador[comprador.pk]
            itens = []
            for lote in escolhidos:
                qtd = Decimal(round(self.rng.uniform(kmin, kmax)))
                qtd = min(qtd, restante[id(lote)].to_integral_value(rounding="ROUND_FLOOR"))
                if qtd < 1:
                    continue
                if status != "cancelado":
                    restante[id(lote)] -= qtd
                itens.append((lote, dec(qtd)))
            if not itens:
                continue

            data_pedido = self.momento(dia, 6, 21)
            prevista = dia + timedelta(days=self.rng.randint(1, 7))
            entrega = None
            if status == "entregue":
                entrega = prevista + timedelta(days=self.rng.choices([-1, 0, 0, 0, 1, 2, 3])[0])
                entrega = min(max(entrega, dia), DATA_REFERENCIA)
            peso_total = sum(q for _l, q in itens)
            mesmo_municipio = comprador.municipio == produtores[produtor_id].municipio
            if mesmo_municipio:
                frete = self.rng.choice([0, 0, 30, 50, 80])
            else:
                frete = 60 + float(peso_total) * self.rng.uniform(0.04, 0.12)
            if comprador.tipo == "exportador":
                frete = 0  # FOB: exportador retira no packing
            pedidos.append(Pedido(
                codigo=f"PD{dia:%y%m}-{len(pedidos) + 1:05d}", comprador=comprador,
                produtor=produtores[produtor_id], status=status,
                forma_pagamento=self.rng.choices(
                    ["pix", "boleto", "transferencia", "prazo_30", "dinheiro"],
                    weights=[45, 15, 15, 15 if comprador.tipo != "feirante" else 2,
                             10 if comprador.tipo == "feirante" else 2])[0],
                data_pedido=data_pedido, data_entrega_prevista=prevista, data_entrega=entrega,
                endereco_entrega=f"{comprador.endereco}, {comprador.municipio}-{comprador.uf}",
                valor_frete=dec(frete),
                observacoes=self.rng.choice(["", "", "", "Entregar pela manhã.", "Ligar antes de sair.",
                                             "Paletizar a carga.", "Nota fiscal em nome da empresa."]),
            ))
            itens_por_pedido.append(itens)

        # Estoque final e status dos lotes
        for lote in self.lotes:
            lote.quantidade_disponivel_kg = dec(restante[id(lote)])
            dias = (DATA_REFERENCIA - lote.data_colheita).days
            if id(lote) in cancelado_lote:
                lote.status = "cancelado"
            elif lote.quantidade_disponivel_kg < 1 or dias > lote.validade_dias + 10:
                lote.status = "esgotado"
                if dias > lote.validade_dias + 10:
                    lote.quantidade_disponivel_kg = Decimal("0.00")
            elif self.rng.random() < 0.12:
                lote.status = "reservado"
        self.lotes = self.bulk(Lote, self.lotes)

        self.pedidos = self.bulk(Pedido, pedidos)
        ItemPedido.objects.bulk_create([
            ItemPedido(pedido=p, lote=lote, quantidade_kg=q, preco_unitario=lote.preco_kg)
            for p, itens in zip(self.pedidos, itens_por_pedido) for lote, q in itens
        ])

    def criar_avaliacoes(self):
        objs = []
        for pedido in self.pedidos:
            if pedido.status != "entregue" or self.rng.random() > 0.72:
                continue
            atraso = (pedido.data_entrega - pedido.data_entrega_prevista).days
            pontualidade = 5 if atraso <= 0 else max(1, 5 - atraso - self.rng.randint(0, 1))
            qualidade = self.rng.choices([5, 4, 3, 2, 1], weights=[45, 32, 13, 7, 3])[0]
            nota = max(1, min(5, round(qualidade * 0.7 + pontualidade * 0.3 + self.rng.uniform(-0.4, 0.4))))
            objs.append(Avaliacao(
                pedido=pedido, nota=nota, qualidade_fruta=qualidade, pontualidade=pontualidade,
                comentario=self.rng.choice(COMENTARIOS[nota] + [""]),
                criada_em=self.momento(min(pedido.data_entrega + timedelta(days=self.rng.randint(0, 5)),
                                           DATA_REFERENCIA), 7, 22),
            ))
        Avaliacao.objects.bulk_create(objs)

    def criar_cotacoes(self):
        """Série diária (dias úteis) simulada por passeio aleatório com reversão à média."""
        objs, usd, razao_eur = [], 5.45, 1.09
        dia = INICIO_COTACOES
        while dia <= DATA_REFERENCIA:
            if dia.weekday() < 5:
                usd += (5.50 - usd) * 0.02 + self.rng.gauss(0, 0.035)
                usd = min(max(usd, 4.90), 6.40)
                razao_eur += (1.10 - razao_eur) * 0.03 + self.rng.gauss(0, 0.003)
                for moeda, venda in (("USD", usd), ("EUR", usd * razao_eur)):
                    spread = venda * self.rng.uniform(0.0002, 0.0012)
                    objs.append(CotacaoCambio(
                        moeda=moeda, data=dia, venda=dec(venda, Decimal("0.0001")),
                        compra=dec(venda - spread, Decimal("0.0001")), fonte="Simulado (Faker)",
                    ))
            dia += timedelta(days=1)
        CotacaoCambio.objects.bulk_create(objs)

    # ------------------------------------------------------------------ #
    def imprimir_resumo(self):
        User = get_user_model()
        linhas = [
            ("Usuários (auth.User)", User.objects.count()),
            ("Certificações", Certificacao.objects.count()),
            ("Culturas", Cultura.objects.count()),
            ("Produtores", Produtor.objects.count()),
            ("Propriedades", Propriedade.objects.count()),
            ("  Propriedade × Cultura (M2M)", Propriedade.culturas.through.objects.count()),
            ("  Propriedade × Certificação (M2M)", Propriedade.certificacoes.through.objects.count()),
            ("Lotes", Lote.objects.count()),
            ("Compradores", Comprador.objects.count()),
            ("Pedidos", Pedido.objects.count()),
            ("Itens de pedido", ItemPedido.objects.count()),
            ("Avaliações", Avaliacao.objects.count()),
            ("Cotações de câmbio", CotacaoCambio.objects.count()),
        ]
        self.stdout.write(self.style.SUCCESS("\nBanco populado com sucesso!\n"))
        largura = max(len(n) for n, _ in linhas)
        for nome, qtd in linhas:
            self.stdout.write(f"  {nome.ljust(largura)}  {qtd:>6}")
        self.stdout.write(f"\nAdmin: usuário '{ADMIN_USUARIO}' / senha '{ADMIN_SENHA}'")
