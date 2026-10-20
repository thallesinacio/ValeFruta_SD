from django import forms

from .models import Lote


class LoteForm(forms.ModelForm):
    class Meta:
        model = Lote
        fields = [
            "propriedade", "cultura", "classificacao", "destino",
            "quantidade_kg", "quantidade_disponivel_kg", "preco_kg",
            "data_colheita", "validade_dias", "observacoes",
        ]
        widgets = {
            "data_colheita": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, produtor=None, **kwargs):
        super().__init__(*args, **kwargs)
        # o produtor só pode escolher as propriedades dele
        if produtor is not None:
            self.fields["propriedade"].queryset = produtor.propriedades.all()
