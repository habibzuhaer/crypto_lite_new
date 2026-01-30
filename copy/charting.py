# charting.py
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from typing import List, Dict, Any
import numpy as np
from strategy_levels import get_all_ema_series, rsi_series


def plot_png(
    candles: List[Dict[str, Any]],
    levels: Dict[str, float],
    out_path: str,
    title: str = "",
    *args,
    **kwargs
) -> str:
    if not candles or not levels:
        raise ValueError("candles or levels empty")

    # 80% для цен, 20% для RSI
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [8, 2]})

    # ── фон ───────────────────────────────────────────
    fig.patch.set_facecolor("#0e1117")
    ax1.set_facecolor("#0e1117")
    ax2.set_facecolor("#0e1117")

    # ── данные свечей ────────────────────────────────────────
    def _normalize_candle(c):
        return {
            "ts": int(c.get("ts") or c.get("timestamp") or 0),
            "open": float(c.get("open") or c.get("o") or 0.0),
            "high": float(c.get("high") or c.get("h") or 0.0),
            "low": float(c.get("low") or c.get("l") or 0.0),
            "close": float(c.get("close") or c.get("c") or 0.0),
        }
    
    norm_candles = [_normalize_candle(c) for c in candles]
    
    xs = list(range(len(norm_candles)))
    opens = [c["open"] for c in norm_candles]
    closes = [c["close"] for c in norm_candles]
    highs = [c["high"] for c in norm_candles]
    lows = [c["low"] for c in norm_candles]
    
    timestamps = [c["ts"] for c in norm_candles]

    # ── свечи ─────────────────────────────────────────
    body_width = 0.7
    wick_width = 0.8

    for i, (o, c, h, l) in enumerate(zip(opens, closes, highs, lows)):
        # Цвета как на TradingView
        color = "#26a69a" if c >= o else "#ef5350"
        
        # Тени
        ax1.vlines(i, l, h, color=color, linewidth=wick_width, alpha=0.8)
        
        # Тело
        bottom = min(o, c)
        height = abs(c - o)
        if height > 0:
            ax1.add_patch(
                plt.Rectangle(
                    (i - body_width / 2, bottom),
                    body_width,
                    height,
                    facecolor=color,
                    edgecolor=color,
                    linewidth=0
                )
            )
        else:
            # Додж-свеча (цена не изменилась)
            ax1.hlines(o, i - body_width/2, i + body_width/2, color=color, linewidth=1)

    # ── уровни (с подписями слева) ─────────────────────
    if levels:
        # Важные уровни для отображения
        important_levels = ["X", "F", "A", "C", "D", "Y"]
        level_color = "#FFD700"  # Золотистый
        
        # Собираем уровни
        level_values = []
        for name in important_levels:
            if name in levels:
                level_values.append((name, levels[name]))
        
        # Рисуем уровни
        for name, value in level_values:
            # Горизонтальная линия на всем графике
            ax1.axhline(y=value, color=level_color, linestyle='--', linewidth=0.8, alpha=0.7)
            
            # Подпись уровня слева
            ax1.text(
                -1,  # Левее начала свечей
                value,
                f"{name} = {value:.4f}",
                color=level_color,
                fontsize=9,
                va='center',
                ha='right',
                backgroundcolor='#0e1117',
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#0e1117", 
                         edgecolor=level_color, alpha=0.8)
            )

    # ── EMA линии ─────────────────────────────────────
    try:
        ema_series = get_all_ema_series(norm_candles)
        
        # Цвета EMA
        ema_settings = {
            "EMA_8": {"color": "#FF6B00", "label": "EMA-8", "linewidth": 1.0},
            "EMA_54": {"color": "#00D6D6", "label": "EMA-54", "linewidth": 1.0},
            "EMA_78": {"color": "#FF00FF", "label": "EMA-78", "linewidth": 1.0},
            "EMA_200": {"color": "#FFFFFF", "label": "EMA-200", "linewidth": 1.5}
        }
        
        # Отрисовываем линии EMA
        for ema_key, settings in ema_settings.items():
            if ema_key in ema_series and ema_series[ema_key]:
                values = ema_series[ema_key]
                # Фильтруем None значения
                valid_indices = [i for i, v in enumerate(values) if v is not None]
                valid_values = [v for v in values if v is not None]
                
                if valid_indices:
                    ax1.plot(
                        valid_indices,
                        valid_values,
                        color=settings["color"],
                        linewidth=settings["linewidth"],
                        label=settings["label"],
                        alpha=0.9
                    )
        
        # Легенда EMA в правом верхнем углу
        ax1.legend(loc='upper right', fontsize=9, facecolor="#0e1117", 
                  edgecolor="#555555", labelcolor="white", framealpha=0.8)
        
    except Exception as e:
        print(f"[CHART] Ошибка отрисовки EMA: {e}")

    # ── выделение базовой свечи ────────────────────────
    if "_base_ts" in levels:
        base_ts = levels["_base_ts"]
        for i, ts in enumerate(timestamps):
            if ts == base_ts and i < len(norm_candles):
                candle = norm_candles[i]
                # Вертикальная линия на позиции базовой свечи
                ax1.axvline(x=i, color='yellow', linewidth=1, alpha=0.3, linestyle='-')
                
                # Пометка сверху
                ax1.text(
                    i,
                    candle["high"] * 1.02,
                    'BASE',
                    color='yellow',
                    fontsize=8,
                    ha='center',
                    va='bottom',
                    backgroundcolor='#0e1117',
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#0e1117", 
                             edgecolor='yellow', alpha=0.8)
                )
                break

    # ── RSI индикатор ────────────────────────────────
    try:
        rsi_values = rsi_series(norm_candles, 14)
        
        valid_indices = []
        valid_rsi = []
        for i, val in enumerate(rsi_values):
            if val is not None:
                valid_indices.append(i)
                valid_rsi.append(val)
        
        if valid_rsi:
            # Основная линия RSI
            ax2.plot(valid_indices, valid_rsi, color="#2196F3", linewidth=1.5)
            
            # Уровни
            ax2.axhline(y=70, color='#ef5350', linestyle='--', linewidth=0.8, alpha=0.6)
            ax2.axhline(y=30, color='#26a69a', linestyle='--', linewidth=0.8, alpha=0.6)
            ax2.axhline(y=50, color='#777777', linestyle='--', linewidth=0.5, alpha=0.3)
            
            # Зоны
            ax2.fill_between(valid_indices, 70, 100, color='#ef5350', alpha=0.1)
            ax2.fill_between(valid_indices, 0, 30, color='#26a69a', alpha=0.1)
            
            ax2.set_ylim(0, 100)
            ax2.set_ylabel("RSI14", color="white", fontsize=10)
            ax2.set_xlabel("Bars", color="white", fontsize=10)
            
    except Exception as e:
        print(f"[CHART] Ошибка отрисовки RSI: {e}")

    # ── оформление ────────────────────────────────────
    ax1.set_title(title, color="white", fontsize=14, fontweight='bold', pad=20)
    
    # Сетка
    ax1.grid(True, color="#2a2a2a", alpha=0.5, linestyle='-', linewidth=0.5)
    ax2.grid(True, color="#2a2a2a", alpha=0.3, linestyle='-', linewidth=0.5)
    
    # Цвета осей
    ax1.tick_params(colors="white", labelsize=10)
    ax2.tick_params(colors="white", labelsize=10)
    
    # Цвет рамок
    for spine in ax1.spines.values():
        spine.set_color("#666666")
    for spine in ax2.spines.values():
        spine.set_color("#666666")
    
    # Пределы осей X (без больших отступов)
    ax1.set_xlim(0, len(candles) - 1)
    ax2.set_xlim(0, len(candles) - 1)
    
    # Скрываем метки X на верхнем графике
    ax1.set_xticklabels([])
    
    # Настройка оси Y для цен
    if norm_candles:
        # Все цены (свечи + уровни)
        all_prices = []
        for c in norm_candles:
            all_prices.extend([c["high"], c["low"]])
        
        if levels:
            for key in ["X", "F", "A", "C", "D", "Y"]:
                if key in levels:
                    all_prices.append(levels[key])
        
        if all_prices:
            min_price = min(all_prices)
            max_price = max(all_prices)
            price_range = max_price - min_price
            
            # Небольшой отступ (1%)
            padding = price_range * 0.01
            ax1.set_ylim(min_price - padding, max_price + padding)
            
            # Форматирование цен
            from matplotlib.ticker import FormatStrFormatter
            ax1.yaxis.set_major_formatter(FormatStrFormatter('%.4f'))
            
            # Больше делений для лучшей читаемости
            ax1.yaxis.set_major_locator(plt.MaxNLocator(20))

    # ── сохранение ────────────────────────────────────
    fig.tight_layout()
    fig.subplots_adjust(hspace=0.05)  # Минимальное расстояние между графиками
    
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), 
               edgecolor='none', bbox_inches='tight')
    plt.close(fig)

    return out_path