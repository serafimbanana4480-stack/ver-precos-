"""
Testes de regressão para a extração de preço do Autoline.

Cada caso abaixo veio da base de produção (auditoria de 06/08/2026), onde 43%
dos preços "extraídos com sucesso" estavam errados. Se algum destes voltar a
passar, o parser regrediu.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "autoline_lightweight",
    Path(__file__).resolve().parent.parent / "scrapers" / "autoline_lightweight.py")
al = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(al)


def extract_price(title: str):
    """Replica o caminho de extração de preço do scraper."""
    price = None
    for m in al.EURO_RE.finditer(title):
        v = al._to_num(m.group(1))
        if v and al.PRICE_MIN <= v <= al.PRICE_MAX:
            price = v
    return price if al._price_is_plausible(price, title) else None


# Títulos reais que produziam preços absurdos na base.
BAD_CASES = [
    # designação de motor lida como preço
    ("Dacia Duster 1.5 dCi 9 Dacia Duster 1.5 dCi 150 € Crossover", "dCi 150"),
    ("Peugeot 207 CC 17 Peugeot 207 CC 100 € Cabriolet 2007", "valor abaixo do plausível"),
    # número do modelo concatenado com o preço
    ("Renault ZOE R90 8 Renault ZOE R90 150 € Hatchback", "R90 + 150 -> 90150"),
    ("Peugeot 407 33 Peugeot 407 500 € Sem impostos Sedan 2006", "407 + 500 -> 407500"),
    ("Peugeot 308 13 Peugeot 308 100 € Sem impostos Hatchback", "308 + 100 -> 308100"),
]

GOOD_CASES = [
    ("Peugeot 208 SUV 12.500 € 85.000 km", 12500.0),
    ("Volkswagen Golf 1.6 TDI 18.500 € Hatchback 2019", 18500.0),
    ("Renault Clio 1.5 dCi 8.750 € Hatchback 2016 145.000 km", 8750.0),
    ("BMW Serie 5 Berlina 1 044 € 136.018 km", 1044.0),
]

FOREIGN_CASES = [
    "BMW 525i 46 BMW 525i 1 124 € 8 400 DKK Carro 1985 136 018 km",
    "Audi Q4 E-tron 30 Audi Q4 E-tron 18 940 € 209 500 SEK Crossover 2023",
    "Volvo V60 Cross Country 39 Volvo V60 23 490 € 259 900 SEK Carrinha 2021",
]


@pytest.mark.parametrize("title,motivo", BAD_CASES)
def test_rejeita_precos_absurdos(title, motivo):
    assert extract_price(title) is None, f"devia rejeitar ({motivo}): {title}"


@pytest.mark.parametrize("title,esperado", GOOD_CASES)
def test_aceita_precos_validos(title, esperado):
    assert extract_price(title) == esperado


@pytest.mark.parametrize("title", FOREIGN_CASES)
def test_bloqueia_moeda_estrangeira(title):
    """O autoline.pt agrega leilões suecos e dinamarqueses."""
    assert al._has_foreign_currency(title) is True


def test_moeda_portuguesa_nao_e_bloqueada():
    assert al._has_foreign_currency("Peugeot 208 SUV 12.500 € 85.000 km") is False


def test_ano_extrai_quatro_digitos():
    """Regressão: group(2) devolvia só o século ('20'), não o ano."""
    import re
    m = re.search(r"(Año|Ano)\s+((?:19|20)\d{2})", "carro Peugeot 208 Ano 2018 SUV")
    assert int(m.group(2)) == 2018


def test_limites_de_plausibilidade():
    assert al._price_is_plausible(799, "Carro qualquer") is False
    assert al._price_is_plausible(800, "Carro qualquer") is True
    assert al._price_is_plausible(250_001, "Carro qualquer") is False
