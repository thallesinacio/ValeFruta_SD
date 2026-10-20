from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoteForm
from .models import Lote, Produtor


def produtor_logado(request):
    try:
        return request.user.produtor
    except Produtor.DoesNotExist:
        return None


def gerar_codigo_lote(data_colheita):
    prefixo = f"VF{data_colheita:%y}-"
    seq = Lote.objects.filter(codigo__startswith=prefixo).count() + 1
    while Lote.objects.filter(codigo=f"{prefixo}{seq:05d}").exists():
        seq += 1
    return f"{prefixo}{seq:05d}"


@login_required
def lista_lotes(request):
    produtor = produtor_logado(request)
    if produtor is None:
        messages.error(request, "Apenas produtores podem acessar os lotes.")
        return redirect("login")

    lotes = (Lote.objects.filter(propriedade__produtor=produtor)
             .select_related("propriedade", "cultura")
             .order_by("-criado_em")[:50])
    return render(request, "produtores/lista_lotes.html", {"produtor": produtor, "lotes": lotes})


@login_required
def novo_lote(request):
    produtor = produtor_logado(request)
    if produtor is None:
        messages.error(request, "Apenas produtores podem cadastrar lotes.")
        return redirect("login")

    if request.method == "POST":
        form = LoteForm(request.POST, produtor=produtor)
        if form.is_valid():
            lote = form.save(commit=False)
            lote.codigo = gerar_codigo_lote(lote.data_colheita)
            lote.save()
            messages.success(request, f"Lote {lote.codigo} cadastrado com sucesso!")
            return redirect("lista_lotes")
        messages.error(request, "Não foi possível cadastrar o lote. Corrija os erros abaixo.")
    else:
        form = LoteForm(produtor=produtor)

    return render(request, "produtores/novo_lote.html", {"form": form})
