"""Diagnostic: quantos 'dados_insuficientes' sao resgaveis pelo reference/ML."""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from valuation.service import load_market_rows, ValuationService
from valuation.market_reference import estimate_reference_value, validate_estimate
from valuation.predict import PricePredictor

AUCTION = frozenset({"LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA",
                     "AUTOLINE", "MARTELO", "PENHORADO", "ELEILOES"})


def main():
    rows = [r for r in load_market_rows(limit=None)
            if r.get("price") and 300 <= float(r["price"]) <= 500000]
    rows = [r for r in rows if str(r.get("source", "")).upper() not in AUCTION]
    print("eligible", len(rows))
    t0 = time.time()
    svc = ValuationService.from_rows(rows)
    print("index", round(time.time() - t0, 1), "s")
    ml = PricePredictor("carros")
    ins = 0
    ref_ok = 0
    ml_ok = 0
    both = 0
    ref_errs = 0.0
    ml_errs = 0.0
    ref_by_conf = {}
    for r in rows:
        est = svc.evaluate(r).estimate
        if est.value is None:
            ins += 1
            price = float(r["price"])
            fuel = str(r.get("fuel_type") or "")
            rr = estimate_reference_value(
                brand=r.get("brand"), model=r.get("model"),
                year=r.get("year"), km=r.get("km"),
                fuel_type=fuel, vehicle_type="carros")
            chk = validate_estimate(rr["value"] or 0, r, asking_price=price)
            ok_ref = (rr["value"] is not None
                      and rr["confidence"] >= 0.35
                      and chk["is_valid"])
            try:
                mp = ml.predict(r)
            except Exception:
                mp = None
            ok_ml = mp is not None and 300 <= mp <= 500000
            if ok_ref:
                ref_ok += 1
                ref_errs += abs(rr["value"] - price)
                b = round(rr["confidence"], 1)
                ref_by_conf[b] = ref_by_conf.get(b, 0) + 1
            if ok_ml:
                ml_ok += 1
                ml_errs += abs(mp - price)
            if ok_ref and ok_ml:
                both += 1
    print("insufficient:", ins)
    print("rescuable by reference:", ref_ok,
          "-> mean_abs_err ~", round(ref_errs / max(ref_ok, 1), 0))
    print("rescuable by ml:", ml_ok,
          "-> mean_abs_err ~", round(ml_errs / max(ml_ok, 1), 0))
    print("both:", both)
    print("ref by confidence bucket:", dict(sorted(ref_by_conf.items())))
    print("elapsed", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
