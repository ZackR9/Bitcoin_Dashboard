import pandas as pd


def summarize(classes):
    """classes: list of dicts with name, value_cad, cost_cad (None when unknown).

    Cash is passed with cost_cad == value_cad so it counts as invested with zero
    return. Classes with cost_cad None (e.g. balance fetch failed) are valued
    but excluded from the P&L figures."""
    total_value = sum(c.get("value_cad") or 0 for c in classes)
    known = [c for c in classes if c.get("cost_cad") is not None]
    total_cost = sum(c["cost_cad"] for c in known)
    known_value = sum(c.get("value_cad") or 0 for c in known)
    pnl = known_value - total_cost
    allocation = pd.DataFrame(
        [{"asset_class": c["name"], "value_cad": c.get("value_cad") or 0} for c in classes]
    )
    # Entries may be per-asset (multiple rows per class); aggregate for the chart.
    allocation = allocation.groupby("asset_class", as_index=False)["value_cad"].sum()
    allocation = allocation[allocation["value_cad"] > 0]
    return {
        "total_value_cad": total_value,
        "total_cost_cad": total_cost,
        "pnl_cad": pnl,
        "pnl_pct": pnl / total_cost * 100 if total_cost > 0 else None,
        "allocation": allocation,
    }
