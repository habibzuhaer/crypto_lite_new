#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# liquidity_range.py - Liquidity Range Engine аналогичный TradingView

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

@dataclass
class LiquidityRange:
    """Класс для хранения состояния ликвидость-ранжа."""
    high: float
    low: float
    start_idx: int
    start_ts: int
    state: int  # 0=WAIT, 1=RANGE, 2=INSIDE, 3=READY
    false_count: int = 0
    inside_bars: int = 0
    
    def is_inside(self, price: float) -> bool:
        """Проверяет, находится ли цена внутри диапазона."""
        return self.low <= price <= self.high
    
    def is_above(self, price: float) -> bool:
        """Проверяет, находится ли цена выше диапазона."""
        return price > self.high
    
    def is_below(self, price: float) -> bool:
        """Проверяет, находится ли цена ниже диапазона."""
        return price < self.low
    
    def get_center(self) -> float:
        """Возвращает центр диапазона."""
        return (self.high + self.low) / 2
    
    def get_width(self) -> float:
        """Возвращает ширину диапазона."""
        return self.high - self.low


class LiquidityRangeEngine:
    """Движок ликвидость-ранжей аналогичный TradingView индикатору."""
    
    def __init__(
        self,
        atr_length: int = 14,
        impulse_atr_mult: float = 1.8,
        range_atr_mult: float = 0.5,
        false_bars_max: int = 2,
        accumulation_bars: int = 5,
        impulse_body_mult: float = 1.5,
        max_lifetime: int = 80
    ):
        """
        Args:
            atr_length: Длина ATR
            impulse_atr_mult: Множитель ATR для импульсной свечи
            range_atr_mult: Ширина диапазона (множитель ATR)
            false_bars_max: Максимум ложных пробоев
            accumulation_bars: Баров для накопления
            impulse_body_mult: Множитель тела свечи для импульсного пробоя
            max_lifetime: Максимальная жизнь диапазона в барах
        """
        self.atr_length = atr_length
        self.impulse_atr_mult = impulse_atr_mult
        self.range_atr_mult = range_atr_mult
        self.false_bars_max = false_bars_max
        self.accumulation_bars = accumulation_bars
        self.impulse_body_mult = impulse_body_mult
        self.max_lifetime = max_lifetime
        
        # Текущий активный диапазон
        self.current_range: Optional[LiquidityRange] = None
        
        # История диапазонов
        self.ranges_history: List[LiquidityRange] = []
        
        logging.info(f"[LRE] Инициализирован с параметрами: ATR={atr_length}, Импульс×{impulse_atr_mult}")
    
    def calculate_atr(self, candles: List[Dict]) -> float:
        """Рассчитывает ATR для последней свечи."""
        if len(candles) < self.atr_length + 1:
            return 0.0
        
        # Нормализуем свечи
        def norm(c):
            return {
                "high": float(c.get("high", c.get("h", 0))),
                "low": float(c.get("low", c.get("l", 0))),
                "close": float(c.get("close", c.get("c", 0))),
            }
        
        norm_candles = [norm(c) for c in candles]
        
        # Расчет True Range
        tr_values = []
        for i in range(1, len(norm_candles)):
            prev_close = norm_candles[i-1]["close"]
            high = norm_candles[i]["high"]
            low = norm_candles[i]["low"]
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            tr = max(tr1, tr2, tr3)
            tr_values.append(tr)
        
        # Берем последние N значений для ATR
        if len(tr_values) >= self.atr_length:
            atr = sum(tr_values[-self.atr_length:]) / self.atr_length
            return atr
        elif tr_values:
            atr = sum(tr_values) / len(tr_values)
            return atr
        
        return 0.0
    
    def calculate_avg_body(self, candles: List[Dict]) -> float:
        """Рассчитывает среднее тело свечи за 20 периодов."""
        if len(candles) < 20:
            return 0.0
        
        bodies = []
        for candle in candles[-20:]:
            open_price = float(candle.get("open", candle.get("o", 0)))
            close_price = float(candle.get("close", candle.get("c", 0)))
            body = abs(close_price - open_price)
            bodies.append(body)
        
        return sum(bodies) / len(bodies) if bodies else 0.0
    
    def detect_impulse(self, candle: Dict, atr: float) -> bool:
        """Определяет, является ли свеча импульсной."""
        if atr == 0:
            return False
        
        high = float(candle.get("high", candle.get("h", 0)))
        low = float(candle.get("low", candle.get("l", 0)))
        candle_range = high - low
        
        return candle_range >= atr * self.impulse_atr_mult
    
    def update(self, candles: List[Dict], current_idx: int) -> Dict:
        """
        Основной метод обновления состояния.
        
        Returns:
            Словарь с информацией о текущем состоянии
        """
        if len(candles) < 2:
            return {"state": 0, "message": "Недостаточно данных"}
        
        last_candle = candles[-1]
        current_ts = int(last_candle.get("ts", last_candle.get("timestamp", 0)))
        current_close = float(last_candle.get("close", last_candle.get("c", 0)))
        current_high = float(last_candle.get("high", last_candle.get("h", 0)))
        current_low = float(last_candle.get("low", last_candle.get("l", 0)))
        current_open = float(last_candle.get("open", last_candle.get("o", 0)))
        
        # Расчет индикаторов
        atr = self.calculate_atr(candles)
        avg_body = self.calculate_avg_body(candles)
        current_body = abs(current_close - current_open)
        
        result = {
            "state": 0,
            "atr": atr,
            "avg_body": avg_body,
            "message": "",
            "range_info": None
        }
        
        # === STATE 0: WAIT - Ожидание импульсной свечи ===
        if self.current_range is None:
            impulse = self.detect_impulse(last_candle, atr)
            
            if impulse and atr > 0:
                # Создаем новый диапазон
                center = (current_high + current_low) / 2
                half_range = atr * self.range_atr_mult
                
                range_high = center + half_range
                range_low = center - half_range
                
                self.current_range = LiquidityRange(
                    high=range_high,
                    low=range_low,
                    start_idx=current_idx,
                    start_ts=current_ts,
                    state=1  # Переходим в состояние RANGE
                )
                
                result["state"] = 1
                result["message"] = f"Импульс обнаружен! Диапазон: {range_low:.4f}-{range_high:.4f}"
                result["range_info"] = {
                    "high": range_high,
                    "low": range_low,
                    "center": center,
                    "width": half_range * 2
                }
                
                logging.info(f"[LRE] STATE 0→1: Новый диапазон создан: {range_low:.4f}-{range_high:.4f}")
            
            else:
                result["state"] = 0
                result["message"] = "Ожидание импульсной свечи"
        
        # === STATE 1: RANGE - Диапазон установлен ===
        elif self.current_range.state == 1:
            # Увеличиваем счетчик баров внутри диапазона
            self.current_range.inside_bars += 1
            
            # Проверяем, вошла ли цена в диапазон
            if self.current_range.is_inside(current_close):
                self.current_range.state = 2  # Переходим в INSIDE
                result["state"] = 2
                result["message"] = f"Цена вошла в диапазон {self.current_range.low:.4f}-{self.current_range.high:.4f}"
                result["range_info"] = {
                    "high": self.current_range.high,
                    "low": self.current_range.low,
                    "center": self.current_range.get_center(),
                    "width": self.current_range.get_width(),
                    "inside_bars": self.current_range.inside_bars
                }
                
                logging.info(f"[LRE] STATE 1→2: Цена вошла в диапазон")
            
            else:
                result["state"] = 1
                result["message"] = f"Ожидание входа в диапазон {self.current_range.low:.4f}-{self.current_range.high:.4f}"
                result["range_info"] = {
                    "high": self.current_range.high,
                    "low": self.current_range.low,
                    "center": self.current_range.get_center(),
                    "width": self.current_range.get_width(),
                    "inside_bars": self.current_range.inside_bars
                }
        
        # === STATE 2: INSIDE - Цена внутри диапазона ===
        elif self.current_range.state == 2:
            self.current_range.inside_bars += 1
            
            # Проверяем ложные пробои
            false_up = current_high > self.current_range.high and current_close < self.current_range.high
            false_down = current_low < self.current_range.low and current_close > self.current_range.low
            
            if false_up or false_down:
                self.current_range.false_count += 1
                
                if self.current_range.false_count <= self.false_bars_max:
                    direction = "ВВЕРХ" if false_up else "ВНИЗ"
                    result["message"] = f"Ложный пробой {direction}! Счётчик: {self.current_range.false_count}/{self.false_bars_max}"
                    logging.info(f"[LRE] Ложный пробой {direction}")
            
            # Проверяем завершение накопления
            if self.current_range.inside_bars >= self.accumulation_bars:
                self.current_range.state = 3  # Переходим в READY
                result["state"] = 3
                result["message"] = f"Накопление завершено! Готов к импульсному пробою"
                logging.info(f"[LRE] STATE 2→3: Накопление завершено")
            
            else:
                result["state"] = 2
                result["message"] = f"Накопление: {self.current_range.inside_bars}/{self.accumulation_bars} баров"
            
            result["range_info"] = {
                "high": self.current_range.high,
                "low": self.current_range.low,
                "center": self.current_range.get_center(),
                "width": self.current_range.get_width(),
                "inside_bars": self.current_range.inside_bars,
                "false_count": self.current_range.false_count,
                "state": self.current_range.state
            }
        
        # === STATE 3: READY - Ждем импульсный пробой ===
        elif self.current_range.state == 3:
            # Увеличиваем счетчик баров
            self.current_range.inside_bars += 1
            
            # Проверяем импульсный пробой
            impulse_up = current_close > self.current_range.high and current_body >= avg_body * self.impulse_body_mult
            impulse_down = current_close < self.current_range.low and current_body >= avg_body * self.impulse_body_mult
            
            if impulse_up or impulse_down:
                direction = "ВВЕРХ" if impulse_up else "ВНИЗ"
                
                # Сохраняем в историю
                self.ranges_history.append(self.current_range)
                
                result["state"] = 0
                result["message"] = f"ИМПУЛЬСНЫЙ ПРОБОЙ {direction}! Диапазон завершен"
                result["range_info"] = {
                    "high": self.current_range.high,
                    "low": self.current_range.low,
                    "direction": direction,
                    "breakout_price": current_close,
                    "state": 0  # Возвращаемся в состояние 0
                }
                
                logging.info(f"[LRE] STATE 3→0: Импульсный пробой {direction}!")
                
                # Сбрасываем текущий диапазон
                self.current_range = None
            
            else:
                result["state"] = 3
                result["message"] = f"Ожидание импульсного пробоя"
                result["range_info"] = {
                    "high": self.current_range.high,
                    "low": self.current_range.low,
                    "center": self.current_range.get_center(),
                    "width": self.current_range.get_width(),
                    "inside_bars": self.current_range.inside_bars,
                    "state": self.current_range.state
                }
        
        # === ПРОВЕРКА ИСТЕЧЕНИЯ ВРЕМЕНИ ===
        if self.current_range and (current_idx - self.current_range.start_idx) > self.max_lifetime:
            # Сохраняем в историю
            self.ranges_history.append(self.current_range)
            
            result["state"] = 0
            result["message"] = f"Диапазон истёк (максимум {self.max_lifetime} баров)"
            result["range_info"] = {
                "high": self.current_range.high,
                "low": self.current_range.low,
                "reason": "timeout",
                "state": 0
            }
            
            logging.info(f"[LRE] Диапазон истёк по времени")
            
            # Сбрасываем текущий диапазон
            self.current_range = None
        
        return result
    
    def get_current_range_info(self) -> Optional[Dict]:
        """Возвращает информацию о текущем диапазоне."""
        if self.current_range:
            return {
                "high": self.current_range.high,
                "low": self.current_range.low,
                "center": self.current_range.get_center(),
                "width": self.current_range.get_width(),
                "state": self.current_range.state,
                "start_idx": self.current_range.start_idx,
                "start_ts": self.current_range.start_ts,
                "inside_bars": self.current_range.inside_bars,
                "false_count": self.current_range.false_count
            }
        return None
    
    def get_history(self) -> List[Dict]:
        """Возвращает историю завершенных диапазонов."""
        history = []
        for r in self.ranges_history:
            history.append({
                "high": r.high,
                "low": r.low,
                "center": r.get_center(),
                "width": r.get_width(),
                "start_ts": r.start_ts,
                "inside_bars": r.inside_bars,
                "false_count": r.false_count,
                "state_at_close": r.state
            })
        return history
    
    def reset(self):
        """Сбрасывает состояние движка."""
        self.current_range = None
        self.ranges_history = []
        logging.info("[LRE] Состояние сброшено")


# Глобальный экземпляр для каждого символа/ТФ
_liquidity_engines: Dict[str, LiquidityRangeEngine] = {}

def get_liquidity_engine(symbol: str, tf: str) -> LiquidityRangeEngine:
    """Возвращает или создает движок ликвидость-ранжей для пары."""
    key = f"{symbol}|{tf}"
    
    if key not in _liquidity_engines:
        _liquidity_engines[key] = LiquidityRangeEngine(
            atr_length=14,
            impulse_atr_mult=1.8,
            range_atr_mult=0.5,
            false_bars_max=2,
            accumulation_bars=5,
            impulse_body_mult=1.5,
            max_lifetime=80
        )
    
    return _liquidity_engines[key]