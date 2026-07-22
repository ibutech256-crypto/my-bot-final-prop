from datetime import datetime, timezone, timedelta
from decimal import Decimal
from intelligence.resampling import CustomTimeframeEngine
from intelligence.smart_fvg import SmartFairValueGapEngine
from intelligence.symbol_mapping import SmartSymbolMappingEngine
from intelligence.killzone import HardKillZoneEngine
from trading_engine.types import Candle

def c(i,o,h,l,cl): return Candle(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i),Decimal(o),Decimal(h),Decimal(l),Decimal(cl),Decimal('1'),True)

def test_69m_resampling():
    candles=[c(i,'1','2','0.5',str(Decimal('1')+Decimal(i)/Decimal('1000'))) for i in range(140)]
    bars=CustomTimeframeEngine().resample_minutes(candles,69)
    assert len(bars)==3
    assert bars[0].open==Decimal('1')

def test_smart_fvg_midpoint_invalidation():
    candles=[c(0,'1.00','1.02','0.99','1.01'),c(1,'1.01','1.04','1.00','1.03'),c(2,'1.06','1.08','1.05','1.07'),c(3,'1.07','1.075','1.00','1.01')]
    gaps=SmartFairValueGapEngine().detect(candles)
    assert gaps[-1].invalidated is True
    assert SmartFairValueGapEngine().confluence_score(gaps[-1]) == Decimal('0')

def test_symbol_mapping_suffixes():
    mapper=SmartSymbolMappingEngine()
    assert mapper.map('BTCUSD',['BTCUSDm','ETHUSD']) == 'BTCUSDm'
    assert mapper.map('NAS100',['NAS100.cash','US30.cash']) == 'NAS100.cash'

def test_hard_killzone_blocks_outside_window():
    allowed,_=HardKillZoneEngine().evaluate(datetime(2026,1,1,7,30,tzinfo=timezone.utc))
    blocked,_=HardKillZoneEngine().evaluate(datetime(2026,1,1,4,30,tzinfo=timezone.utc))
    assert allowed and not blocked

from intelligence.data_freshness import TimestampValidationEngine
from intelligence.resampling_cache import ResamplerCache

def test_timestamp_validation_rejects_stale_data():
    now = datetime(2026,1,1,12,0,0,tzinfo=timezone.utc)
    stale = now - timedelta(milliseconds=501)
    result = TimestampValidationEngine().validate(stale, now)
    assert result.fresh is False

def test_resampler_cache_cleanup_removes_expired_entries():
    cache = ResamplerCache(ttl_minutes=1, max_entries=10)
    cache.set('EURUSD:69', ['bars'])
    stats = cache.cleanup(datetime.now(timezone.utc) + timedelta(minutes=2))
    assert stats.entries == 0
