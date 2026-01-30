"""
ENGINE: Детектор маржинальных зон давления (логика CME).
Генерирует события состояний (ZoneState), не торговые сигналы.
Интеграция: в основной цикл бота, после получения новых свечей.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Dict, Any
import logging

class ZoneState(Enum):
    """Фаза жизненного цикла маржинальной зоны."""
    WAIT = auto()
    CREATED = auto()
    ENTERED = auto()
    FALSE_BREAK = auto()
    HOLD = auto()
    EXIT_IMPULSE = auto()
    EXPIRED = auto()

@dataclass
class Candle:
    """Универсальный адаптер свечи."""
    ts: int
    open: float
    high: float
    low: float
    close: float
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Candle':
        return cls(
            ts=int(data.get('timestamp', data.get('time', 0))),
            open=float(data['open']),
            high=float(data['high']),
            low=float(data['low']),
            close=float(data['close'])
        )

@dataclass
class MarginZoneConfig:
    """Конфигурация алгоритма."""
    atr_period: int = 14
    impulse_atr_mult: float = 1.8
    zone_width_atr: float = 0.5
    false_break_max: int = 2
    hold_bars: int = 5
    impulse_exit_body_mult: float = 1.5
    max_zone_lifetime: int = 80

@dataclass
class MarginZone:
    """Экземпляр маржинальной зоны."""
    zone_id: str
    symbol: str
    timeframe: str
    center: float
    upper: float
    lower: float
    created_at: int
    state: ZoneState
    false_break_count: int = 0
    inside_bars: int = 0

def calculate_atr(candles: List[Candle], period: int) -> Optional[float]:
    """Расчёт ATR."""
    if len(candles) < period + 1:
        return None
    
    tr_sum = 0.0
    for i in range(1, period + 1):
        curr = candles[-i]
        prev = candles[-i - 1]
        tr = max(
            curr.high - curr.low,
            abs(curr.high - prev.close),
            abs(curr.low - prev.close)
        )
        tr_sum += tr
    
    return tr_sum / period

class MarginZoneEngine:
    """Основной класс движка."""
    
    def __init__(self, symbol: str, timeframe: str, config: Optional[MarginZoneConfig] = None):
        self.symbol = symbol
        self.timeframe = timeframe
        self.cfg = config or MarginZoneConfig()
        self.active_zone: Optional[MarginZone] = None
        self.candle_history: List[Candle] = []
        self.logger = logging.getLogger(f"MarginZone.{symbol}")
        
    def update_candles(self, new_candles: List[Dict[str, Any]]) -> None:
        """Загрузка свечей в движок."""
        self.candle_history = [Candle.from_dict(c) for c in new_candles]
        
    def process(self) -> Optional[ZoneState]:
        """Основной метод обработки. Возвращает событие или None."""
        if len(self.candle_history) < self.cfg.atr_period + 1:
            return None
            
        last_candle = self.candle_history[-1]
        atr = calculate_atr(self.candle_history, self.cfg.atr_period)
        if atr is None:
            return None
            
        # Создание новой зоны при импульсе
        if not self.active_zone:
            if self._is_impulse(last_candle, atr):
                self.active_zone = self._create_zone(last_candle, atr)
                self.logger.info(f"Зона CREATED: {self.active_zone.upper:.2f}-{self.active_zone.lower:.2f}")
                return ZoneState.CREATED
            return None
            
        # Обработка существующей зоны
        event = self._process_zone(self.active_zone, last_candle, atr)
        if event:
            self.logger.info(f"Событие: {event.name}")
            if event in (ZoneState.EXIT_IMPULSE, ZoneState.EXPIRED):
                self.active_zone = None
        return event
        
    def _is_impulse(self, candle: Candle, atr: float) -> bool:
        """Детектор импульсной свечи."""
        return (candle.high - candle.low) >= atr * self.cfg.impulse_atr_mult
        
    def _create_zone(self, candle: Candle, atr: float) -> MarginZone:
        """Создание зоны от midpoint импульсной свечи."""
        center = (candle.high + candle.low) / 2
        half_width = atr * self.cfg.zone_width_atr
        
        return MarginZone(
            zone_id=f"{self.symbol}_{self.timeframe}_{candle.ts}",
            symbol=self.symbol,
            timeframe=self.timeframe,
            center=center,
            upper=center + half_width,
            lower=center - half_width,
            created_at=candle.ts,
            state=ZoneState.CREATED
        )
        
    def _process_zone(self, zone: MarginZone, candle: Candle, atr: float) -> Optional[ZoneState]:
        """Логика обработки состояния зоны."""
        # 1. Проверка срока жизни
        if zone.inside_bars > self.cfg.max_zone_lifetime:
            zone.state = ZoneState.EXPIRED
            return ZoneState.EXPIRED
            
        # 2. Проверка входа в зону
        inside = zone.lower <= candle.close <= zone.upper
        if zone.state == ZoneState.CREATED and inside:
            zone.state = ZoneState.ENTERED
            zone.inside_bars = 1
            return ZoneState.ENTERED
            
        # 3. Логика внутри зоны
        if zone.state in (ZoneState.ENTERED, ZoneState.FALSE_BREAK, ZoneState.HOLD):
            if inside:
                zone.inside_bars += 1
            else:
                zone.inside_bars = 0
                
            # Ложный выход
            false_up = candle.high > zone.upper and candle.close < zone.upper
            false_dn = candle.low < zone.lower and candle.close > zone.lower
            if false_up or false_dn:
                zone.false_break_count += 1
                zone.state = ZoneState.FALSE_BREAK
                return ZoneState.FALSE_BREAK
                
            # Удержание
            if zone.inside_bars >= self.cfg.hold_bars:
                zone.state = ZoneState.HOLD
                return ZoneState.HOLD
                
        # 4. Импульсный выход
        avg_body = self._get_avg_body()
        if avg_body:
            body = abs(candle.close - candle.open)
            impulse_up = candle.close > zone.upper and body >= avg_body * self.cfg.impulse_exit_body_mult
            impulse_dn = candle.close < zone.lower and body >= avg_body * self.cfg.impulse_exit_body_mult
            if impulse_up or impulse_dn:
                zone.state = ZoneState.EXIT_IMPULSE
                return ZoneState.EXIT_IMPULSE
        
        return None
        
    def _get_avg_body(self, lookback: int = 20) -> Optional[float]:
        """Средний размер тела свечи."""
        if len(self.candle_history) < lookback:
            return None
        bodies = [abs(c.close - c.open) for c in self.candle_history[-lookback:]]
        return sum(bodies) / len(bodies)
        
    def get_zone_info(self) -> Optional[Dict[str, Any]]:
        """Информация о текущей зоне для логов."""
        if not self.active_zone:
            return None
            
        z = self.active_zone
        return {
            'id': z.zone_id,
            'symbol': z.symbol,
            'upper': z.upper,
            'lower': z.lower,
            'state': z.state.name,
            'inside_bars': z.inside_bars,
            'false_breaks': z.false_break_count,
            'center': z.center
        }