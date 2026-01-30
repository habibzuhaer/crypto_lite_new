# charting.py
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from typing import List, Dict, Any


def plot_png(
    candles: List[Dict[str, Any]],
    levels: Dict[str, float],
    out_path: str,
    title: str = "",
    *_,
    **__
) -> str:
    if not candles or not levels:
        raise ValueError("candles or levels empty")

    fig, ax = plt.subplots(figsize=(14, 6))

    # ── фон ───────────────────────────────────────────
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    # ── данные ────────────────────────────────────────
    xs = list(range(len(candles)))
    opens  = [c["open"] for c in candles]
    closes = [c["close"] for c in candles]
    highs  = [c["high"] for c in candles]
    lows   = [c["low"] for c in candles]

    # ── свечи ─────────────────────────────────────────
    body_width = 0.6

    for i, (o, c, h, l) in enumerate(zip(opens, closes, highs, lows)):
        color = "#2ecc71" if c >= o else "#e74c3c"

        # тень
        ax.vlines(i, l, h, color=color, linewidth=1)

        # тело
        bottom = min(o, c)
        height = abs(c - o)
        ax.add_patch(
            plt.Rectangle(
                (i - body_width / 2, bottom),
                body_width,
                height if height > 1e-12 else 1e-12,
                facecolor=color,
                edgecolor=color,
                linewidth=0
            )
        )

    # ── уровни ────────────────────────────────────────
    level_color = "#d4af37"

    for name in ["X", "D", "C", "A", "F", "Y"]:
        if name not in levels:
            continue
        y = levels[name]
        ax.hlines(
            y,
            xmin=0,
            xmax=len(candles) - 1,
            colors=level_color,
            linestyles="dashed",
            linewidth=1,
            alpha=0.85
        )
        ax.text(
            len(candles) + 1,
            y,
            name,
            color=level_color,
            fontsize=9,
            va="center",
            ha="left"
        )

    # ── маркер базовой свечи ──────────────────────────
    if "base_idx" in levels:
        bi = levels["base_idx"]
        if 0 <= bi < len(candles):
            ax.plot(
                bi,
                highs[bi],
                marker="v",
                color="yellow",
                markersize=8
            )

    # ── оформление ────────────────────────────────────
    ax.set_title(title, color="white", fontsize=11)
    ax.grid(True, color="#444444", alpha=0.4)

    ax.tick_params(colors="white", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#555555")

    ax.set_xlim(-1, len(candles) + 6)

    # ── сохранение ────────────────────────────────────
    fig.canvas.draw()          # КРИТИЧНО
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return out_path
