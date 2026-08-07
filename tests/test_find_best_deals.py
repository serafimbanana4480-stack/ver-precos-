"""Testes do ranking de negócios por lucro líquido realista.

Sem base de dados e sem rede: as dependências pesadas (carregamento de
veículos e avaliação) são injetadas por monkeypatch. O que se testa é a
política de seleção e ordenação, que é onde o dinheiro se ganha ou perde.
"""
from __future__ import annotations

import pytest

from scripts import find_best_deals as fbd
from valuation.realism import ProfitAudit


def make_row(
    *, vid: int, profit: float, roi_annual: float, verdict: str = "negocio",
    confidence: float = 0.8, worst: float | None = None, source: str = "OLX",
) -> fbd.DealRow:
    audit = ProfitAudit(
        verdict=verdict,
        confidence=confidence,
        net_profit=profit,
        net_profit_worst_case=profit if worst is None else worst,
        roi_annualized_pct=roi_annual,
        roi_pct=roi_annual / 6,
    )
    return fbd.DealRow(
        vehicle_id=vid, source=source, url=f"https://x.pt/{vid}",
        title=f"Carro {vid}", brand="BMW", model="320d",
        year=2018, km=120000, asking_price=15000.0, audit=audit,
    )


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Substitui carregamento e avaliação por dados controlados."""
    def _install(rows):
        vehicles = [{"id": r.vehicle_id} for r in rows]
        by_id = {r.vehicle_id: r for r in rows}
        monkeypatch.setattr(fbd, "load_candidates", lambda **_: vehicles)
        monkeypatch.setattr(fbd, "evaluate", lambda v: by_id.get(v["id"]))
    return _install


class TestSelection:
    def test_only_actionable_verdicts(self, stub_pipeline):
        stub_pipeline([
            make_row(vid=1, profit=2000, roi_annual=90, verdict="negocio"),
            make_row(vid=2, profit=9000, roi_annual=400, verdict="suspeito"),
            make_row(vid=3, profit=1500, roi_annual=70, verdict="marginal"),
            make_row(vid=4, profit=-500, roi_annual=-20, verdict="sem_margem"),
            make_row(vid=5, profit=3000, roi_annual=120, verdict="indeterminado"),
        ])
        report = fbd.find_best_deals(top=10)
        ids = [d["id"] for d in report["negocios"]]
        assert ids == [1]

    def test_suspect_included_on_request(self, stub_pipeline):
        """Suspeitos são para investigar, não para comprar — por isso opt-in."""
        stub_pipeline([
            make_row(vid=1, profit=2000, roi_annual=90),
            make_row(vid=2, profit=9000, roi_annual=400, verdict="suspeito"),
        ])
        report = fbd.find_best_deals(top=10, include_suspect=True)
        assert {d["id"] for d in report["negocios"]} == {1, 2}

    def test_min_profit_filter(self, stub_pipeline):
        stub_pipeline([
            make_row(vid=1, profit=400, roi_annual=50),
            make_row(vid=2, profit=1200, roi_annual=60),
        ])
        report = fbd.find_best_deals(top=10, min_profit=750)
        assert [d["id"] for d in report["negocios"]] == [2]

    def test_low_confidence_is_excluded(self, stub_pipeline):
        # Um lucro grande sobre uma avaliação em que não se confia continua
        # a ser um palpite; não entra na lista de acção.
        stub_pipeline([
            make_row(vid=1, profit=5000, roi_annual=300, confidence=0.1),
            make_row(vid=2, profit=1000, roi_annual=50, confidence=0.8),
        ])
        report = fbd.find_best_deals(top=10, min_confidence=0.35)
        assert [d["id"] for d in report["negocios"]] == [2]


class TestOrdering:
    def test_sorts_by_annualised_roi(self, stub_pipeline):
        """€1.000 em 30 dias vale mais que €1.500 em 180: o capital roda."""
        stub_pipeline([
            make_row(vid=1, profit=1500, roi_annual=40),
            make_row(vid=2, profit=1000, roi_annual=200),
            make_row(vid=3, profit=1200, roi_annual=110),
        ])
        report = fbd.find_best_deals(top=10)
        assert [d["id"] for d in report["negocios"]] == [2, 3, 1]

    def test_absolute_profit_breaks_ties(self, stub_pipeline):
        stub_pipeline([
            make_row(vid=1, profit=1000, roi_annual=100),
            make_row(vid=2, profit=2500, roi_annual=100),
        ])
        report = fbd.find_best_deals(top=10)
        assert [d["id"] for d in report["negocios"]] == [2, 1]

    def test_respects_top(self, stub_pipeline):
        stub_pipeline([
            make_row(vid=i, profit=1000 + i, roi_annual=50 + i) for i in range(1, 11)
        ])
        assert len(fbd.find_best_deals(top=3)["negocios"]) == 3


class TestReport:
    def test_counts_every_verdict(self, stub_pipeline):
        stub_pipeline([
            make_row(vid=1, profit=2000, roi_annual=90, verdict="negocio"),
            make_row(vid=2, profit=100, roi_annual=5, verdict="marginal"),
            make_row(vid=3, profit=-800, roi_annual=-30, verdict="sem_margem"),
            make_row(vid=4, profit=-100, roi_annual=-5, verdict="sem_margem"),
        ])
        report = fbd.find_best_deals(top=10)
        assert report["analisados"] == 4
        assert report["distribuicao_veredito"] == {
            "marginal": 1, "negocio": 1, "sem_margem": 2
        }

    def test_row_payload_is_actionable(self, stub_pipeline):
        stub_pipeline([make_row(vid=1, profit=2000, roi_annual=90)])
        deal = fbd.find_best_deals(top=1)["negocios"][0]
        # Os campos que permitem decidir e negociar têm de estar presentes.
        for key in (
            "preco_pedido", "venda_realista", "lucro_liquido", "lucro_pior_caso",
            "preco_maximo_compra", "custos", "iva_margem", "roi_anualizado_pct",
            "confianca", "riscos", "url",
        ):
            assert key in deal, key

    def test_empty_result_is_valid(self, stub_pipeline):
        stub_pipeline([])
        report = fbd.find_best_deals(top=10)
        assert report["negocios"] == []
        assert report["analisados"] == 0

    def test_evaluation_failure_is_counted_not_crashed(self, stub_pipeline, monkeypatch):
        stub_pipeline([make_row(vid=1, profit=2000, roi_annual=90)])
        monkeypatch.setattr(fbd, "evaluate", lambda v: None)
        report = fbd.find_best_deals(top=10)
        assert report["distribuicao_veredito"]["sem_estimativa"] == 1


class TestCountryMapping:
    @pytest.mark.parametrize("source,country", [
        ("AUTOSCOUT24_DE", "DE"),
        ("AUTOSCOUT24_ES", "ES"),
        ("AUTOSCOUT24_FR", "FR"),
        ("OLX", "PT"),
        ("ELEILOES", "PT"),
    ])
    def test_country_drives_isv_and_transport(self, source, country):
        # Sem este mapeamento um carro alemão seria custeado como nacional.
        assert fbd._country_for(source) == country
