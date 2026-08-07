"""Testes da calibração conformal de intervalos."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_SPEC = importlib.util.spec_from_file_location(
    "interval_calibration",
    Path(__file__).resolve().parent.parent / "valuation" / "interval_calibration.py")
ic = importlib.util.module_from_spec(_SPEC)
# @dataclass precisa do módulo registado para resolver as anotações
sys.modules["interval_calibration"] = ic
_SPEC.loader.exec_module(ic)


def _synthetic(n=500, seed=0, tightness=0.05):
    """Intervalos deliberadamente demasiado estreitos, como os heurísticos."""
    rng = np.random.default_rng(seed)
    true = rng.uniform(2_000, 70_000, n)
    center = true * rng.normal(1.0, 0.15, n)
    lo = center * (1 - tightness)
    hi = center * (1 + tightness)
    return lo, hi, center, true


def test_calibracao_atinge_cobertura_alvo():
    lo, hi, mid, y = _synthetic()
    cal = ic.IntervalCalibrator(target_coverage=0.80).fit(lo, hi, mid, y)
    r = cal.report_
    assert r.coverage_before < 50, "cenário devia começar mal calibrado"
    assert r.coverage_after >= 75, f"cobertura pós-calibração insuficiente: {r.coverage_after}"


def test_calibracao_alarga_e_nao_estreita():
    lo, hi, mid, y = _synthetic()
    cal = ic.IntervalCalibrator().fit(lo, hi, mid, y)
    assert cal.global_factor >= 1.0
    assert cal.report_.median_width_after >= cal.report_.median_width_before


def test_apply_marca_fiabilidade_e_publicavel():
    lo, hi, mid, y = _synthetic()
    cal = ic.IntervalCalibrator().fit(lo, hi, mid, y)
    out = cal.apply({"estimated_value": 20_000, "value_low": 19_000,
                     "value_high": 21_000})
    assert out["value_low_calibrated"] < 19_000
    assert out["value_high_calibrated"] > 21_000
    assert out["interval_reliability"] in ("alta", "media", "baixa")
    assert isinstance(out["publishable"], bool)
    assert out["estimated_value"] == 20_000, "a estimativa central não deve mudar"


def test_intervalo_muito_largo_nao_e_publicavel():
    cal = ic.IntervalCalibrator()
    cal.global_factor = 1.0
    out = cal.apply({"estimated_value": 3_000, "value_low": 500,
                     "value_high": 9_000})
    assert out["publishable"] is False
    assert out["interval_reliability"] == "baixa"


def test_valuation_invalida_e_rejeitada():
    cal = ic.IntervalCalibrator()
    out = cal.apply({"estimated_value": 0, "value_low": 0, "value_high": 0})
    assert out["publishable"] is False
    assert out["interval_reliability"] == "insuficiente"


def test_persistencia(tmp_path):
    lo, hi, mid, y = _synthetic()
    p = tmp_path / "cal.json"
    cal = ic.IntervalCalibrator(path=p).fit(lo, hi, mid, y)
    cal.save()
    loaded = ic.IntervalCalibrator.load(p)
    assert loaded is not None
    assert loaded.global_factor == pytest.approx(cal.global_factor)
    assert loaded.factors == pytest.approx(cal.factors)


def test_load_sem_ficheiro_devolve_none(tmp_path):
    assert ic.IntervalCalibrator.load(tmp_path / "nao_existe.json") is None


def test_amostra_pequena_e_recusada():
    lo, hi, mid, y = _synthetic(n=10)
    with pytest.raises(ValueError, match="calibração precisa"):
        ic.IntervalCalibrator().fit(lo, hi, mid, y)


def test_bandas_de_preco():
    assert ic.band_of(3_000) == "0k-5k"
    assert ic.band_of(20_000) == "15k-30k"
    assert ic.band_of(200_000) == "60k+"
