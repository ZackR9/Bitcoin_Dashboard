"""Tiny shared formatting helpers for the views."""


def cad(x):
    return f"${x:,.2f}"


def sign_pct(x):
    """'+1.23%' / '-0.45%', em dash when unknown."""
    return f"{x:+.2f}%" if x is not None else "—"
