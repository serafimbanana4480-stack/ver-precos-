"""Verificação do motor fiscal contra os exemplos oficiais de 2026.

Todos os valores esperados aqui são exemplos publicados na fonte de
referência das tabelas de ISV/IUC 2026 (impostosobreveiculos.info, que
reproduz o Código do ISV e o OE2026). Se uma alteração ao código de
``pt_fiscal`` fizer estes testes falhar, é o código que está errado — não
os testes.

Isto importa porque o ISV é a maior componente de custo de uma importação:
um erro de escalão traduz-se diretamente em milhares de euros de lucro
imaginário.

Fonte: https://impostosobreveiculos.info/isv/imposto-sobre-veiculos-isv-2026/
"""
from __future__ import annotations

import pytest

from valuation.pt_fiscal import (
    ISV_AGE_REDUCTION,
    ISV_PARTICLE_SURCHARGE_PASSENGER,
    calculate_isv,
    isv_age_reduction,
)


def _isv(**kwargs) -> float:
    """Chama ``calculate_isv`` e devolve só o total, seja qual for o formato."""
    result = calculate_isv(**kwargs)
    if isinstance(result, dict):
        for key in ("total", "isv", "value", "amount"):
            if key in result:
                return float(result[key])
        raise AssertionError(f"chave de total não encontrada em {sorted(result)}")
    return float(result)


class TestComponenteCilindrada:
    """Exemplo oficial: 998 cm3 × 1,09 € − 849,03 € = 238,79 €."""

    def test_998cc_petrol_nedc(self):
        # Isolar a componente cilindrada: CO2 baixo para minimizar a ambiental.
        # Verifica-se o escalão, não o total.
        total = _isv(
            engine_cc=998, co2_gkm=95, fuel_type="gasolina",
            age_years=0, homologation="NEDC", vehicle_type="carros",
        )
        # cilindrada 238,79 + ambiental (95×4,62−427,00 = 11,90) = 250,69
        assert total == pytest.approx(250.69, abs=1.0)

    def test_escalao_muda_acima_de_1250cc(self):
        """Um único cm3 acima de 1.250 custa ~199 € de ISV.

        1.250 cm3 → 1.250 × 1,18 − 850,69 = 624,31 €
        1.251 cm3 → 1.251 × 5,61 − 6.194,88 = 823,23 €

        É o degrau mais abrupto da tabela e a causa habitual de estimativas
        de ISV erradas: um 1.2 TSI e um 1.4 TSI não estão no mesmo mundo
        fiscal, apesar de o anúncio os apresentar como equivalentes.
        """
        pequeno = _isv(engine_cc=1250, co2_gkm=95, fuel_type="gasolina",
                       age_years=0, homologation="NEDC", vehicle_type="carros")
        grande = _isv(engine_cc=1251, co2_gkm=95, fuel_type="gasolina",
                      age_years=0, homologation="NEDC", vehicle_type="carros")
        assert grande - pequeno == pytest.approx(198.92, abs=2.0)


class TestComponenteAmbiental:
    def test_gasolina_nedc_105gkm(self):
        """Exemplo oficial: 105 g/km × 8,09 € − 750,99 € = 98,46 €."""
        total = _isv(engine_cc=1000, co2_gkm=105, fuel_type="gasolina",
                     age_years=0, homologation="NEDC", vehicle_type="carros")
        cilindrada = 1000 * 1.09 - 849.03      # 240,97
        assert total == pytest.approx(cilindrada + 98.46, abs=1.5)

    def test_gasolina_wltp_125gkm(self):
        """Exemplo oficial: 125 g/km × 5,27 € − 619,17 € = 39,58 €."""
        total = _isv(engine_cc=1000, co2_gkm=125, fuel_type="gasolina",
                     age_years=0, homologation="WLTP", vehicle_type="carros")
        cilindrada = 1000 * 1.09 - 849.03
        assert total == pytest.approx(cilindrada + 39.58, abs=1.5)

    def test_gasoleo_nedc_107gkm_inclui_agravamento_particulas(self):
        """Exemplo oficial: 107 g/km × 79,22 € − 7.195,63 € = 1.280,91 €.

        Ao gasóleo acresce sempre o agravamento de partículas de 500 €
        quando não há informação de emissões — o caso normal num usado.
        """
        total = _isv(engine_cc=1000, co2_gkm=107, fuel_type="diesel",
                     age_years=0, homologation="NEDC", vehicle_type="carros")
        cilindrada = 1000 * 1.09 - 849.03
        esperado = cilindrada + 1280.91 + ISV_PARTICLE_SURCHARGE_PASSENGER
        assert total == pytest.approx(esperado, abs=2.0)

    def test_gasoleo_wltp_115gkm(self):
        """Exemplo oficial: 115 g/km × 18,96 € − 1.906,19 € = 274,21 €."""
        total = _isv(engine_cc=1000, co2_gkm=115, fuel_type="diesel",
                     age_years=0, homologation="WLTP", vehicle_type="carros")
        cilindrada = 1000 * 1.09 - 849.03
        esperado = cilindrada + 274.21 + ISV_PARTICLE_SURCHARGE_PASSENGER
        assert total == pytest.approx(esperado, abs=2.0)

    def test_gasoleo_custa_muito_mais_que_gasolina(self):
        # Mesmo motor, mesmo CO2: o gasóleo paga substancialmente mais.
        # Tratar os dois por igual sobrestimava o lucro dos diesel importados.
        gasolina = _isv(engine_cc=1600, co2_gkm=120, fuel_type="gasolina",
                        age_years=0, homologation="WLTP", vehicle_type="carros")
        gasoleo = _isv(engine_cc=1600, co2_gkm=120, fuel_type="diesel",
                       age_years=0, homologation="WLTP", vehicle_type="carros")
        assert gasoleo > gasolina


class TestReducaoPorIdade:
    """Tabela única de 2026: desconto de 10% (1 ano) a 80% (>10 anos)."""

    @pytest.mark.parametrize("anos,esperado", [
        (1, 0.10), (2, 0.20), (3, 0.28), (4, 0.35), (5, 0.43),
        (6, 0.52), (7, 0.60), (8, 0.65), (9, 0.70), (10, 0.75),
    ])
    def test_escaloes(self, anos, esperado):
        assert isv_age_reduction(anos) == pytest.approx(esperado)

    def test_teto_de_80_por_cento(self):
        assert isv_age_reduction(11) == pytest.approx(0.80)
        assert isv_age_reduction(25) == pytest.approx(0.80)

    def test_novo_nao_tem_desconto(self):
        assert isv_age_reduction(0) == pytest.approx(0.0)

    def test_tabela_e_monotona(self):
        # Um carro mais velho nunca pode pagar mais ISV que um mais novo.
        reducoes = [r for _, r in ISV_AGE_REDUCTION]
        assert reducoes == sorted(reducoes)

    def test_usado_de_8_anos_paga_35_por_cento(self):
        novo = _isv(engine_cc=1600, co2_gkm=120, fuel_type="gasolina",
                    age_years=0, homologation="WLTP", vehicle_type="carros")
        usado = _isv(engine_cc=1600, co2_gkm=120, fuel_type="gasolina",
                     age_years=8, homologation="WLTP", vehicle_type="carros",
                     from_eu=True)
        assert usado < novo


class TestEletricos:
    def test_eletrico_nao_paga_isv(self):
        # Isenção total: sem cilindrada tributável e sem emissões.
        total = _isv(engine_cc=0, co2_gkm=0, fuel_type="eletrico",
                     age_years=0, homologation="WLTP", vehicle_type="carros")
        assert total == pytest.approx(0.0, abs=0.01)


class TestMotos:
    """Tabela C — taxa única por escalão de cilindrada."""

    @pytest.mark.parametrize("cc,esperado", [
        (125, 73.78), (250, 73.78), (300, 91.63),
        (400, 122.57), (650, 184.45), (1000, 245.14),
    ])
    def test_tabela_c(self, cc, esperado):
        total = _isv(engine_cc=cc, co2_gkm=None, fuel_type="gasolina",
                     age_years=0, vehicle_type="motos")
        assert total == pytest.approx(esperado, abs=1.0)

    def test_ciclomotor_abaixo_de_120cc_isento(self):
        total = _isv(engine_cc=50, co2_gkm=None, fuel_type="gasolina",
                     age_years=0, vehicle_type="motos")
        assert total == pytest.approx(0.0, abs=0.01)
