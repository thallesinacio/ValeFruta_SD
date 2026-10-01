# ValeFruta

Vitrine digital que conecta produtores de frutas do Vale do São Francisco
(Petrolina-PE, Juazeiro-BA e região) a compradores: feirantes, mercados,
restaurantes, distribuidores, indústrias de polpa e exportadores.

Projeto da disciplina **Sistemas Distribuídos (CCMP0054) – UNIVASF**, em Python + Django.

---

## Como rodar na máquina virtual da disciplina (`sd`)

O ambiente oficial é a VM criada pelo pacote `sd.zip`
(VirtualBox + Vagrant, Ubuntu 20.04, **Python 3.8 e Django 3.2**).
O projeto é compatível com esse ambiente.

### 1. Onde colocar o projeto

O conteúdo desta pasta deve ficar em `sd\web-folder\pws`, com o `manage.py`
logo no primeiro nível:

```
sd\                         ← pasta onde está o Vagrantfile
 ├── Vagrantfile
 ├── scripts\
 ├── resources\
 └── web-folder\
      └── pws\              ← o projeto ValeFruta fica aqui
           ├── manage.py
           ├── db.sqlite3
           ├── requirements.txt
           ├── produtores\
           ├── pedidos\
           └── valefruta\
```

Dentro da VM essa pasta aparece como `/vagrant/web-folder/pws`. É esse caminho
que o script ao entrar na VM.

### 2. Liberar o acesso pelo `localhost` (uma vez só)

Em alguns computadores, o firewall ou o antivírus do Windows bloqueia o acesso
ao IP da VM (`192.168.56.100`). Para não depender dele, adicione esta linha ao
`Vagrantfile`, logo abaixo da linha comentada `#config.vm.network "forwarded_port"...`:

```ruby
config.vm.network "forwarded_port", guest: 8000, host: 8000
```

Ela redireciona a porta 8000 da VM para a porta 8000 do Windows.

### 3. Ligar a VM

No PowerShell (ou Prompt de Comando), dentro da pasta `sd`:

```
vagrant up
```

Se a VM já estava ligada quando você alterou o `Vagrantfile`, use
`vagrant reload` para aplicar a mudança. Durante a inicialização deve aparecer
a linha `8000 (guest) => 8000 (host)`.

### 4. Entrar na VM

```
vagrant ssh
```

> ⚠️ **O terminal vai parecer travado.** É o comportamento esperado. Ao entrar,
> o script ativa o ambiente virtual, entra em
> `/vagrant/web-folder/pws` e inicia o Django com o depurador `debugpy` em modo
> de espera (`--wait-for-client`). O servidor fica parado até o VS Code se
> conectar na porta 8001.
>
> Para rodar sem depurador, aperte **Ctrl+C**. Vai aparecer o prompt:
> `(venv) vagrant@sd:/vagrant/web-folder/pws$`

### 5. Instalar as dependências (só na primeira vez)

```bash
pip install -r requirements.txt
```

O Django já vem instalado na VM. Na prática este comando só instala o
**Faker**, usado para gerar os dados fictícios.

### 6. Iniciar o servidor

```bash
python manage.py runserver 0:8000
```

O `0:8000` é obrigatório: sem ele o Django só aceita conexões de dentro da
própria VM, e o navegador do Windows não consegue acessar.

Deixe esse terminal aberto enquanto usa o sistema. Para parar o servidor,
use **Ctrl+C**.

### 7. Acessar o admin

No navegador do Windows:

| | |
|---|---|
| **URL** | http://localhost:8000/admin/ |
| **Usuário** | `admin` |
| **Senha** | `admin123` |

Se o seu computador não bloquear a rede da VM, também funciona
http://192.168.56.100:8000/admin/.

### 8. Desligar a VM

Saia da VM com `exit` e, no PowerShell:

```
vagrant halt
```

Prefira `vagrant halt` a `vagrant suspend` ou a simplesmente fechar a janela.
Quando a VM é suspensa e depois retomada, a rede às vezes volta sem configuração.

---

## Como rodar direto no Windows, sem a VM (opcional)

Requer Python 3.8 ou superior.

```
cd caminho\da\pasta\ValeFruta
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

Acesse http://localhost:8000/admin/ com as mesmas credenciais.

> Antes de zipar uma entrega, apague a pasta `.venv`: ela tem centenas de MB e
> não faz parte do projeto.

---

## Recriar os dados fictícios

O `db.sqlite3` já vem com as migrations aplicadas e todas as tabelas populadas.
Para apagar e gerar os dados de novo:

```bash
python manage.py popular_banco --limpar
```

O comando usa Faker `pt_BR` com semente fixa, então sempre gera os mesmos dados.
Ele também recria o superusuário `admin` / `admin123`. Os 550 usuários
fictícios (produtores e compradores) usam a senha `senha123`, mas não têm
acesso ao admin.

Para recriar o banco do zero:

```bash
rm db.sqlite3                      # no Windows: del db.sqlite3
python manage.py migrate
python manage.py popular_banco
```

---

## Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| Terminal parado logo após o `vagrant ssh` | Django esperando o depurador (`debugpy`) | **Ctrl+C** e depois `python manage.py runserver 0:8000` |
| Navegador não abre `192.168.56.100:8000` | Firewall/antivírus do Windows bloqueando a rede da VM | Use o redirecionamento de porta (passo 2) e acesse `localhost:8000` |
| Navegador não abre `localhost:8000` | Servidor rodando sem o `0:` ou VM sem o redirecionamento | Confira o passo 6 e rode `vagrant reload` |
| `vagrant reload` diz que a porta 8000 está em uso | Outro programa usando a porta 8000 no Windows | Troque `host: 8000` por `host: 8080` e acesse `localhost:8080` |
| `database is locked` ou `disk I/O error` | SQLite na pasta compartilhada entre Windows e VM | Copie o projeto para dentro da VM (`cp -r /vagrant/web-folder/pws ~/`) e rode de lá |
| Página abre como `https://` e dá erro | Navegador forçando HTTPS | Digite `http://` no endereço ou use uma aba anônima |

---

## Entrega 2: models, migrations, admin e dados fictícios

### Aplicações e models

| App | Model | Relações principais |
|---|---|---|
| `produtores` | **Certificacao** | M2M com Propriedade |
| | **Cultura** (fruta + variedade) | M2M com Propriedade; 1→N Lote |
| | **Produtor** | 1→1 `User`; 1→N Propriedade; 1→N Pedido |
| | **Propriedade** | N→1 Produtor; M2M Cultura e Certificacao; 1→N Lote |
| | **Lote** | N→1 Propriedade e Cultura; 1→N ItemPedido |
| `pedidos` | **Comprador** | 1→1 `User`; 1→N Pedido |
| | **Pedido** | N→1 Comprador e Produtor; 1→N ItemPedido; 1→1 Avaliacao |
| | **ItemPedido** | N→1 Pedido e Lote |
| | **Avaliacao** | 1→1 Pedido |
| | **CotacaoCambio** | independente (USD/EUR diário) |

### Admin customizado

Todos os models têm `list_display`, `list_filter`, `search_fields`, `ordering`,
`list_per_page`, `autocomplete_fields`, `fieldsets` e colunas calculadas com
`@admin.display`. Os inlines refletem as dependências entre os models:

- **Produtor** → Propriedades → Lotes
- **Comprador** → Pedidos
- **Pedido** → Itens + Avaliação
- **Propriedade** usa `filter_horizontal` para Culturas e Certificações

### Regras de negócio validadas

- Quantidade disponível do lote ≤ quantidade colhida.
- Data de colheita não pode estar no futuro.
- O lote só pode ser de uma cultura cadastrada na propriedade.
- Os itens de um pedido precisam ser lotes do produtor do pedido, sem exceder o estoque.
- Só pedidos entregues podem ser avaliados (no máximo uma avaliação por pedido).
- CPF/CNPJ no formato correto conforme o tipo de pessoa; telefone no formato `(87) 99999-9999`.
- Cotação: venda ≥ compra e uma cotação por moeda por dia.

### Dados fictícios

| Tabela | Registros |
|---|---|
| Usuários | 551 |
| Produtores | 250 |
| Propriedades | 420 |
| Lotes | 1.500 |
| Compradores | 300 |
| Pedidos | 1.200 |
| Itens de pedido | 1.952 |
| Avaliações | 717 |
| Cotações de câmbio | 1.044 |
| Culturas (catálogo) | 42 |
| Certificações (catálogo) | 9 |

Os dados são coerentes com o domínio: municípios e perímetros irrigados do
Vale, variedades reais de manga e uva, preços por kg, safras, pedidos e
avaliações.

### Compatibilidade

Testado com Python 3.8 + Django 3.2.4 (VM da disciplina) e com Python 3.11 + Django 5.2.
