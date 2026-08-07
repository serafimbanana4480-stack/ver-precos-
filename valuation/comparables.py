"""Seleção hierárquica de comparáveis e estimativa robusta com intervalo.

Substitui a hierarquia antiga (que descia até «mesma marca» e «segmento
global», misturando um A 35 AMG com um A 180 d e um Panamera Turbo com um
Panamera base) por níveis que respeitam a identidade do veículo.

Hierarquia (para; nunca desce se o nível já satisfaz o mínimo)
--------------------------------------------------------------
=====  =========================================================  ======
Nível  Critério                                                   Mín.
=====  =========================================================  ======
1      marca+família+performance+combustível+transmissão, ano ±1  3
2      marca+família+performance+combustível, ano ±2              3
3      marca+família+performance, combustível compatível, ano ±3  4
4      marca+família, performance adjacente (±1 escalão), ano ±3  6
=====  =========================================================  ======

Não existe nível "marca" nem "segmento global": a mediana de todos os
Mercedes não é o valor de mercado de nenhum Mercedes em concreto. Quando
nenhum nível reúne comparáveis suficientes, a resposta é **"dados
insuficientes"** — nunca um número inventado.

Estimativa
----------
Mediana ponderada por similaridade, com winsorização e filtro MAD para
outliers, correção hedónica de idade e quilometragem, e intervalo pelos
quantis ponderados alargados pelo erro de amostragem. Cada estimativa
transporta a lista de comparáveis usados e rejeitados, com motivos.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from valuation.canonical_vehicle import (
    CanonicalVehicle,
    canonicalize,
    fuel_compatible,
)
from valuation.market_math import finite, json_safe, round_estimate, round_interval

__all__ = [
    "Comparable",
    "MarketEstimate",
    "ComparableIndex",
    "MIN_COMPARABLES",
]

_CURRENT_YEAR = datetime.now().year

#: Mínimo absoluto de comparáveis para produzir qualquer estimativa. Abaixo
#: disto o sistema declara dados insuficientes — é o requisito central do
#: pedido: preferir "não sei" a inventar.
MIN_COMPARABLES: int = 3

#: Metade máxima do intervalo, em percentagem da mediana. Um intervalo mais
#: largo que ±40 % não é acionável e esconderia carros sobrepreçados "dentro
#: do mercado". Com poucos comparáveis a confiança já desce; o intervalo
#: estreito força a classificação para "requer validação" em vez de "dentro".
MAX_INTERVAL_HALF_PCT: float = 0.40
#: (nível, ano±, exige_transmissao, exige_combustivel_exato,
#:  permite_performance_adjacente, mínimo, penalização de confiança,
#:  similaridade mínima)
_LEVELS: Tuple[Tuple, ...] = (
    (1, 1, True, True, False, 3, 1.00, 0.35),
    (2, 2, False, True, False, 3, 0.92, 0.30),
    (3, 3, False, False, False, 4, 0.82, 0.25),
    (4, 3, False, False, False, 6, 0.72, 0.22),
    # Fallback mais largo para mercados esparsos mas reais: ±4 anos, sem
    # exigência de combustível exato (apenas compatível), similaridade baixa.
    (5, 4, False, False, False, 3, 0.62, 0.18),
)


@dataclass(frozen=True)
class Comparable:
    """Um anúncio usado (ou rejeitado) como referência de mercado."""

    id: Any
    price: float
    year: Optional[int]
    km: Optional[int]
    horsepower: Optional[int] = None
    source: str
    similarity: float
    weight: float
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return json_safe(asdict(self))


@dataclass
class MarketEstimate:
    """Resultado de uma avaliação, com rasto completo.

    ``value is None`` significa literalmente "não consigo estimar", e nesse
    caso ``status == 'dados_insuficientes'``.
    """

    value: Optional[float]
    low: Optional[float]
    high: Optional[float]
    status: str
    method: str
    level: Optional[int]
    comparables_used: int
    comparables_rejected: int
    mean_similarity: Optional[float]
    dispersion_pct: Optional[float]
    confidence: float
    confidence_label: str
    explanation: str
    used: List[Comparable] = field(default_factory=list)
    rejected: List[Comparable] = field(default_factory=list)
    rejection_summary: Dict[str, int] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self, *, include_comparables: bool = False) -> Dict[str, Any]:
        d = {
            "estimated_value": self.value,
            "value_low": self.low,
            "value_high": self.high,
            "status": self.status,
            "method": self.method,
            "reference_level": self.level,
            "comparables_count": self.comparables_used,
            "comparables_rejected": self.comparables_rejected,
            "mean_similarity": self.mean_similarity,
            "dispersion_pct": self.dispersion_pct,
            "confidence": self.confidence,
            "confidence_label": self.confidence_label,
            "valuation_explanation": self.explanation,
            "rejection_summary": self.rejection_summary,
            "notes": self.notes,
        }
        if include_comparables:
            d["comparables_used"] = [c.to_dict() for c in self.used]
            d["comparables_rejected_detail"] = [c.to_dict() for c in self.rejected]
        return json_safe(d)


def _insufficient(
    reason: str, rejected: List[Comparable], summary: Dict[str, int], notes: List[str]
) -> MarketEstimate:
    return MarketEstimate(
        value=None,
        low=None,
        high=None,
        status="dados_insuficientes",
        method="sem_comparaveis_suficientes",
        level=None,
        comparables_used=0,
        comparables_rejected=len(rejected),
        mean_similarity=None,
        dispersion_pct=None,
        confidence=0.0,
        confidence_label="sem_dados",
        explanation=reason,
        used=[],
        rejected=rejected[:50],
        rejection_summary=summary,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Estatística robusta
# ---------------------------------------------------------------------------


def _weighted_quantile(
    values: Sequence[float], weights: Sequence[float], q: float
) -> float:
    """Quantil ponderado por interpolação sobre a CDF acumulada."""
    pairs = sorted(zip(values, weights))
    total = sum(w for _, w in pairs)
    if total <= 0:
        vals = sorted(values)
        return float(vals[min(int(q * len(vals)), len(vals) - 1)])
    cutoff = q * total
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= cutoff:
            return float(v)
    return float(pairs[-1][0])


def _mad_filter(
    comps: List[Comparable], *, threshold: float = 3.5
) -> Tuple[List[Comparable], List[Comparable]]:
    """Remove outliers pelo desvio absoluto mediano (robusto a caudas).

    Usa o z-score modificado de Iglewicz-Hoaglin. Ao contrário do IQR simples,
    não colapsa quando metade da amostra é idêntica. Anúncios com preço
    absurdamente baixo (fraude, entrada, salvado que escapou aos filtros)
    saem daqui e deixam de puxar a mediana para baixo.
    """
    if len(comps) < 4:
        return comps, []
    prices = sorted(c.price for c in comps)
    n = len(prices)
    median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2.0
    deviations = sorted(abs(c.price - median) for c in comps)
    mad = (
        deviations[n // 2]
        if n % 2
        else (deviations[n // 2 - 1] + deviations[n // 2]) / 2.0
    )
    if mad <= 0:
        return comps, []
    kept, dropped = [], []
    for c in comps:
        z = 0.6745 * abs(c.price - median) / mad
        if z > threshold:
            dropped.append(
                Comparable(c.id, c.price, c.year, c.km, c.source, c.similarity,
                           0.0, f"outlier_mad(z={z:.1f})")
            )
        else:
            kept.append(c)
    # Nunca deitar fora mais de 25 % da amostra: se tantos são "outliers",
    # o modelo é que está errado, não os dados.
    if len(dropped) > max(1, len(comps) // 4):
        return comps, []
    return kept, dropped


def _winsorize(values: List[float], pct: float = 0.05) -> List[float]:
    """Trunca as caudas em ``pct`` de cada lado (não remove observações)."""
    if len(values) < 5:
        return values
    ordered = sorted(values)
    k = max(1, int(len(ordered) * pct))
    lo, hi = ordered[k], ordered[-k - 1]
    return [min(max(v, lo), hi) for v in values]


def _fit_km_slope(pairs: Sequence[Tuple[float, float]]) -> Optional[float]:
    """Elasticidade log-log preço↔km, por mínimos quadrados.

    Devolve ``None`` quando não há relação identificável ou a amostra é
    curta. O declive é limitado a ``[-0.45, -0.05]``: fora disso é ruído, e
    extrapolar com ele fabricaria preços.
    """
    pts = [(k, p) for k, p in pairs if k and p and k > 1000 and p > 0]
    if len(pts) < 5:
        return None
    xs = [math.log(k) for k, _ in pts]
    ys = [math.log(p) for _, p in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    if slope > -0.05 or slope < -0.45:
        return None
    return slope


def _fit_hp_slope(pairs: Sequence[Tuple[float, float]]) -> Optional[float]:
    """Elasticidade log-log preço↔potência (cv), por mínimos quadrados.

    Devolve ``None`` se a amostra é curta ou a relação não é plausível. O
    declive é limitado a ``[0.05, 0.55]``: potência maior ⇒ preço maior, mas
    com rendimentos decrescentes (um 400 cv não custa 3× um 200 cv).
    """
    pts = [(h, p) for h, p in pairs if h and p and h >= 40 and p > 0]
    if len(pts) < 5:
        return None
    xs = [math.log(h) for h, _ in pts]
    ys = [math.log(p) for _, p in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    if slope < 0.05 or slope > 0.55:
        return None
    return slope


def _fit_year_slope(pairs: Sequence[Tuple[int, float]]) -> Optional[float]:
    """Depreciação em €/ano estimada sobre os próprios comparáveis."""
    pts = [(y, p) for y, p in pairs if y and p and p > 0]
    years = {y for y, _ in pts}
    if len(pts) < 5 or len(years) < 2:
        return None
    n = len(pts)
    mx = sum(y for y, _ in pts) / n
    my = sum(p for _, p in pts) / n
    den = sum((y - mx) ** 2 for y, _ in pts)
    if den <= 0:
        return None
    slope = sum((y - mx) * (p - my) for y, p in pts) / den
    # Preço tem de subir com o ano do modelo; caso contrário é ruído.
    if slope <= 0:
        return None
    return slope


# ---------------------------------------------------------------------------
# Índice de comparáveis
# ---------------------------------------------------------------------------


class ComparableIndex:
    """Índice em memória de anúncios canonizados, pronto a consultar.

    Construído uma vez por execução a partir das linhas elegíveis da base
    (ver :meth:`from_rows`). Guarda a forma canónica de cada anúncio para
    não repetir o trabalho de normalização por consulta.
    """

    def __init__(self, rows: Sequence[Dict[str, Any]]):
        self.entries: List[Dict[str, Any]] = []
        self._by_family: Dict[Tuple[str, str], List[int]] = {}
        for row in rows:
            price = finite(row.get("price"))
            if price is None or price <= 0:
                continue
            canon = canonicalize(row)
            if canon.brand == "unknown" or canon.model_family == "unknown":
                continue
            idx = len(self.entries)
            self.entries.append(
                {
                    "id": row.get("id"),
                    "price": price,
                    "canon": canon,
                    "source": canon.source,
                    "fingerprint": row.get("fingerprint"),
                    "last_seen": row.get("last_seen"),
                }
            )
            self._by_family.setdefault((canon.brand, canon.model_family), []).append(idx)

    def __len__(self) -> int:
        return len(self.entries)

    @classmethod
    def from_rows(cls, rows: Iterable[Dict[str, Any]]) -> "ComparableIndex":
        return cls(list(rows))

    # -- seleção -----------------------------------------------------------

    def _candidates(self, canon: CanonicalVehicle) -> List[int]:
        return self._by_family.get((canon.brand, canon.model_family), [])

    def estimate(
        self,
        vehicle: Dict[str, Any],
        *,
        exclude_ids: Sequence[Any] = (),
        exclude_fingerprints: Sequence[str] = (),
    ) -> MarketEstimate:
        """Estima o valor de mercado de ``vehicle``.

        O próprio anúncio é sempre excluído dos seus comparáveis (por ``id``
        e por impressão digital), tal como os seus duplicados conhecidos —
        caso contrário o preço pedido entraria no seu próprio target.
        """
        target = canonicalize(vehicle)
        self_id = vehicle.get("id")
        blocked_ids = {self_id, *exclude_ids} - {None}
        self_fp = vehicle.get("fingerprint")
        blocked_fps = {self_fp, *exclude_fingerprints} - {None}

        notes: List[str] = []
        if target.brand == "unknown" or target.model_family == "unknown":
            return _insufficient(
                "Marca ou modelo não identificados: sem base para comparar.",
                [], {"identificacao_insuficiente": 1}, notes,
            )

        pool = self._candidates(target)
        if not pool:
            return _insufficient(
                f"Nenhum anúncio de {target.brand} {target.model_family} na base.",
                [], {"sem_anuncios_do_modelo": 1}, notes,
            )

        rejected: List[Comparable] = []
        summary: Dict[str, int] = {}

        def reject(entry: Dict[str, Any], reason: str) -> None:
            summary[reason] = summary.get(reason, 0) + 1
            if len(rejected) < 200:
                c = entry["canon"]
                rejected.append(
                    Comparable(entry["id"], entry["price"], c.year, c.km,
                               entry["source"], 0.0, 0.0, reason)
                )

        for level, year_span, need_trans, need_fuel, allow_adjacent, min_n, penalty, min_sim in _LEVELS:
            selected: List[Comparable] = []
            level_rejects: List[Tuple[Dict[str, Any], str]] = []
            for i in pool:
                entry = self.entries[i]
                comp = entry["canon"]
                if entry["id"] in blocked_ids:
                    level_rejects.append((entry, "proprio_anuncio_ou_duplicado"))
                    continue
                if entry.get("fingerprint") and entry["fingerprint"] in blocked_fps:
                    level_rejects.append((entry, "proprio_anuncio_ou_duplicado"))
                    continue

                # Performance: nunca misturar escalões distantes.
                dr = abs(comp.performance_rank - target.performance_rank)
                if dr > 0 and not allow_adjacent:
                    level_rejects.append((entry, "versao_de_performance_diferente"))
                    continue
                if dr > 1:
                    level_rejects.append((entry, "versao_de_performance_diferente"))
                    continue

                # Combustível.
                if need_fuel:
                    if comp.fuel != target.fuel or target.fuel == "unknown":
                        level_rejects.append((entry, "combustivel_diferente"))
                        continue
                elif not fuel_compatible(target.fuel, comp.fuel):
                    level_rejects.append((entry, "combustivel_incompativel"))
                    continue

                # Transmissão.
                if need_trans and target.transmission != "unknown":
                    if comp.transmission != target.transmission:
                        level_rejects.append((entry, "transmissao_diferente"))
                        continue

                # Ano.
                if target.year and comp.year:
                    if abs(target.year - comp.year) > year_span:
                        level_rejects.append((entry, "ano_fora_do_intervalo"))
                        continue
                elif target.year and not comp.year:
                    level_rejects.append((entry, "comparavel_sem_ano"))
                    continue

                # Carroçaria: uma carrinha não é uma berlina do mesmo modelo.
                if (
                    target.body != "unknown"
                    and comp.body != "unknown"
                    and comp.body != target.body
                ):
                    level_rejects.append((entry, "carrocaria_diferente"))
                    continue

                similarity = _similarity(target, comp)
                if similarity < min_sim:
                    level_rejects.append((entry, "similaridade_insuficiente"))
                    continue

                selected.append(
                    Comparable(
                        id=entry["id"],
                        price=entry["price"],
                        year=comp.year,
                        km=comp.km,
                        horsepower=comp.horsepower,
                        source=entry["source"],
                        similarity=round(similarity, 3),
                        weight=similarity,
                    )
                )

            if len(selected) < min_n:
                continue

            kept, outliers = _mad_filter(selected)
            if len(kept) < MIN_COMPARABLES:
                continue
            for o in outliers:
                summary[o.reason or "outlier"] = summary.get(o.reason or "outlier", 0) + 1
                rejected.append(o)
            for entry, reason in level_rejects:
                reject(entry, reason)

            return self._build_estimate(
                target, kept, level, penalty, rejected, summary, notes
            )

        # Nenhum nível reuniu comparáveis suficientes: a resposta honesta é
        # "não sei". Os motivos de rejeição já foram acumulados em `summary`.
        for entry, reason in level_rejects:
            reject(entry, reason)
        return _insufficient(
            (
                f"Apenas {len(pool)} anúncio(s) de {target.brand} "
                f"{target.model_family} e nenhum nível reuniu o mínimo de "
                f"{MIN_COMPARABLES} comparáveis compatíveis "
                f"(versão «{target.performance_class}», combustível «{target.fuel}»)."
            ),
            rejected, summary, notes,
        )

    # -- construção do resultado -------------------------------------------

    def _build_estimate(
        self,
        target: CanonicalVehicle,
        comps: List[Comparable],
        level: int,
        penalty: float,
        rejected: List[Comparable],
        summary: Dict[str, int],
        notes: List[str],
    ) -> MarketEstimate:
        # Pesos: similaridade × proximidade de ano × proximidade de km.
        weighted: List[Comparable] = []
        for c in comps:
            w = c.similarity
            if target.year and c.year:
                w *= 1.0 / (1.0 + abs(target.year - c.year))
            if target.km and c.km:
                w *= 1.0 / (1.0 + abs(target.km - c.km) / 60_000.0)
            weighted.append(
                Comparable(c.id, c.price, c.year, c.km, c.source, c.similarity,
                           round(max(w, 1e-6), 5))
            )

        prices = _winsorize([c.price for c in weighted])
        weights = [c.weight for c in weighted]
        center = _weighted_quantile(prices, weights, 0.50)
        q25 = _weighted_quantile(prices, weights, 0.25)
        q75 = _weighted_quantile(prices, weights, 0.75)

        # ── ajustes hedónicos, sempre limitados à vizinhança observada ──────
        adjustments: List[str] = []
        if target.year:
            slope = _fit_year_slope([(c.year, c.price) for c in weighted if c.year])
            comp_years = [c.year for c in weighted if c.year]
            if slope and comp_years:
                med_year = sorted(comp_years)[len(comp_years) // 2]
                delta = target.year - med_year
                if abs(delta) >= 1:
                    shift = max(min(delta * slope, center * 0.25), -center * 0.25)
                    center += shift
                    adjustments.append(
                        f"ajuste de ano {delta:+d} × {slope:,.0f} €/ano".replace(",", ".")
                    )
        if target.km:
            slope = _fit_km_slope([(c.km, c.price) for c in weighted if c.km])
            comp_kms = [c.km for c in weighted if c.km]
            if slope and comp_kms:
                med_km = sorted(comp_kms)[len(comp_kms) // 2]
                if med_km > 0 and abs(med_km - target.km) > 5000:
                    factor = min(max((target.km / med_km) ** slope, 0.75), 1.25)
                    if abs(factor - 1.0) > 0.02:
                        center *= factor
                        adjustments.append(
                            f"ajuste de km {target.km:,.0f} vs {med_km:,.0f} "
                            f"({factor - 1:+.0%})".replace(",", ".")
                        )
        # ── ajuste por potência / cilindrada (mesma família, versões distintas)
        # Um "CLA 200d" (150 cv) vale mais que um "CLA 180" (122 cv); sem isto
        # o motor trata-os como idênticos e a estimativa é a mesma mediana.
        if target.horsepower:
            hp_comps = [(c.horsepower, c.price) for c in weighted if c.horsepower]
            if len(hp_comps) >= 3:
                # elasticidade log-log potência→preço (regressão simples)
                slope = _fit_hp_slope(hp_comps)
                if slope:
                    comp_hps = [h for h, _ in hp_comps]
                    med_hp = sorted(comp_hps)[len(comp_hps) // 2]
                    if med_hp > 0 and abs(med_hp - target.horsepower) >= 10:
                        factor = min(
                            max((target.horsepower / med_hp) ** slope, 0.8), 1.25
                        )
                        if abs(factor - 1.0) > 0.02:
                            center *= factor
                            adjustments.append(
                                f"ajuste de potência {target.horsepower:.0f} vs "
                                f"{med_hp:.0f} cv ({factor - 1:+.0%})".replace(",", ".")
                            )

        # A estimativa nunca sai da vizinhança dos dados observados.
        observed = sorted(c.price for c in weighted)
        floor, ceiling = observed[0] * 0.75, observed[-1] * 1.25
        center = min(max(center, floor), ceiling)

        n = len(weighted)
        mean_sim = sum(c.similarity for c in weighted) / n
        dispersion = (q75 - q25) / center * 100.0 if center > 0 else None

        # ── intervalo ───────────────────────────────────────────────────────
        # Base: IQR ponderado. Alargado pelo erro-padrão da mediana
        # (~1.253·σ/√n), que é o que traduz "poucos comparáveis ⇒ menos certeza".
        # O intervalo NUNCA é mais largo que ±MAX_INTERVAL_HALF_PCT da mediana:
        # um bando de ±190 % (caso n=3 com SEM enorme) não é acionável e serviria
        # para esconder um carro sobrepreçado dentro do "mercado".
        spread = max(q75 - q25, center * 0.04)
        mean_price = sum(observed) / n
        variance = sum((p - mean_price) ** 2 for p in observed) / max(1, n - 1)
        sem = 1.253 * math.sqrt(variance) / math.sqrt(n) if variance > 0 else 0.0
        widen = 1.0 + (1.0 - penalty)
        radius = (spread * 0.5 + 1.96 * sem) * widen
        radius = min(radius, center * MAX_INTERVAL_HALF_PCT)
        low = center - radius
        high = center + radius
        low = max(low, center * 0.55, 300.0)
        high = max(high, center * 1.03)

        # ── confiança ───────────────────────────────────────────────────────
        confidence, label, conf_notes = _score_confidence(
            n=n,
            mean_similarity=mean_sim,
            dispersion_pct=dispersion,
            interval_width_pct=(high - low) / center * 100.0 if center > 0 else None,
            level_penalty=penalty,
            trim_confidence=target.trim_confidence,
            rejected_ratio=(
                len(rejected) / (len(rejected) + n) if (len(rejected) + n) else 0.0
            ),
        )
        notes = notes + conf_notes + adjustments

        width_pct = (high - low) / center * 100.0 if center > 0 else None
        value = round_estimate(center, uncertainty_pct=width_pct)
        r_low, r_high = round_interval(low, high, center)
        if value is not None and r_low is not None and r_high is not None:
            r_low = min(r_low, value)
            r_high = max(r_high, value)

        explanation = (
            f"Mediana ponderada de {n} comparáveis de nível {level} "
            f"({target.brand} {target.model_family}, versão «{target.performance_class}», "
            f"{target.fuel}), similaridade média {mean_sim:.0%}"
            + (f", dispersão {dispersion:.0f}%" if dispersion is not None else "")
            + (". " + "; ".join(adjustments) if adjustments else "")
            + f". Confiança {label}."
        )

        return MarketEstimate(
            value=value,
            low=r_low,
            high=r_high,
            status="ok",
            method=f"comparaveis_nivel_{level}",
            level=level,
            comparables_used=n,
            comparables_rejected=len(rejected),
            mean_similarity=round(mean_sim, 3),
            dispersion_pct=round(dispersion, 2) if dispersion is not None else None,
            confidence=round(confidence, 3),
            confidence_label=label,
            explanation=explanation,
            used=sorted(weighted, key=lambda c: -c.weight)[:30],
            rejected=rejected[:50],
            rejection_summary=summary,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Similaridade e confiança
# ---------------------------------------------------------------------------


def _similarity(target: CanonicalVehicle, comp: CanonicalVehicle) -> float:
    """Similaridade em [0, 1] entre dois veículos canonizados.

    Multiplicativa: cada dimensão discrepante corta a similaridade, e uma
    discrepância grave (escalão de performance) corta-a a metade. Assim, um
    comparável "quase igual" pesa muito mais do que um "parecido".
    """
    score = 1.0
    if target.year and comp.year:
        score *= max(0.25, 1.0 - abs(target.year - comp.year) * 0.14)
    else:
        score *= 0.75
    if target.km and comp.km:
        score *= max(0.35, 1.0 - abs(target.km - comp.km) / 200_000.0)
    else:
        score *= 0.85
    if target.performance_class != comp.performance_class:
        score *= 0.5
    if target.fuel != comp.fuel:
        score *= 0.7
    if target.transmission != "unknown" and comp.transmission != "unknown":
        if target.transmission != comp.transmission:
            score *= 0.85
    if target.drivetrain != comp.drivetrain:
        score *= 0.93
    if target.horsepower and comp.horsepower:
        ratio = min(target.horsepower, comp.horsepower) / max(
            target.horsepower, comp.horsepower
        )
        score *= max(0.5, ratio)
    if target.body != "unknown" and comp.body != "unknown" and target.body != comp.body:
        score *= 0.8
    return max(0.0, min(1.0, score))


def _score_confidence(
    *,
    n: int,
    mean_similarity: float,
    dispersion_pct: Optional[float],
    interval_width_pct: Optional[float],
    level_penalty: float,
    trim_confidence: float,
    rejected_ratio: float,
) -> Tuple[float, str, List[str]]:
    """Confiança medida, não decorativa.

    Regras mínimas impostas (do enunciado):

    * 0 comparáveis → sem estimativa (tratado antes de chegar aqui);
    * 1-2 → ``muito_baixa``; 3-5 → ``baixa``; 6-10 → ``media`` conforme
      dispersão; > 10 muito semelhantes → pode ser ``alta``.
    * Muitos comparáveis pouco semelhantes **nunca** dão confiança alta.
    * Confiança alta exige intervalo estreito.
    """
    notes: List[str] = []
    if n <= 2:
        base = 0.18
    elif n <= 5:
        base = 0.35
    elif n <= 10:
        base = 0.55
    elif n <= 20:
        base = 0.70
    else:
        base = 0.78

    base *= 0.55 + 0.45 * min(1.0, mean_similarity / 0.85)
    if mean_similarity < 0.6:
        notes.append("comparáveis pouco semelhantes ao veículo alvo")

    if dispersion_pct is not None:
        if dispersion_pct > 60:
            base *= 0.6
            notes.append(f"dispersão de preços muito alta ({dispersion_pct:.0f}%)")
        elif dispersion_pct > 35:
            base *= 0.8
            notes.append(f"dispersão de preços alta ({dispersion_pct:.0f}%)")

    base *= level_penalty
    base *= 0.6 + 0.4 * min(1.0, trim_confidence / 0.9)
    if trim_confidence < 0.6:
        notes.append("versão/acabamento não identificado com confiança")

    if rejected_ratio > 0.8:
        base *= 0.85
        notes.append(f"{rejected_ratio:.0%} dos candidatos foram rejeitados")

    confidence = max(0.0, min(0.95, base))

    # Teto duro: confiança alta exige intervalo estreito e amostra densa.
    if interval_width_pct is not None and interval_width_pct > 30 and confidence >= 0.65:
        confidence = 0.62
        notes.append(
            f"intervalo largo ({interval_width_pct:.0f}%) impede confiança alta"
        )
    if n < 6 and confidence >= 0.45:
        confidence = 0.44
    if n < 3:
        confidence = min(confidence, 0.2)

    if confidence >= 0.65:
        label = "alta"
    elif confidence >= 0.45:
        label = "media"
    elif confidence >= 0.25:
        label = "baixa"
    else:
        label = "muito_baixa"
    return confidence, label, notes
