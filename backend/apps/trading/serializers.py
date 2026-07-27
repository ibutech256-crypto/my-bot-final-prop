from rest_framework import serializers
from backend.apps.trading.models import BrokerProfile,BrokerSetting,TradingAccount,TradingSymbol,Watchlist,Signal,Order,OpenPosition,ClosedTrade,TradeJournal

class BrokerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=BrokerProfile; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class BrokerSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model=BrokerSetting; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class TradingAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model=TradingAccount; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class TradingSymbolSerializer(serializers.ModelSerializer):
    class Meta:
        model=TradingSymbol; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class WatchlistSerializer(serializers.ModelSerializer):
    class Meta:
        model=Watchlist; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class SignalSerializer(serializers.ModelSerializer):
    symbol_name = serializers.CharField(source="symbol.symbol", read_only=True)
    confidence_tier = serializers.SerializerMethodField()
    def get_confidence_tier(self, obj):
        c = float(obj.confidence)
        if c >= 85: return "VERY_STRONG"
        if c >= 70: return "STRONG"
        if c >= 55: return "VALID"
        if c >= 50: return "EMERGING"
        return "WEAK"
    class Meta:
        model=Signal; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class OrderSerializer(serializers.ModelSerializer):
    symbol_name = serializers.CharField(source="symbol.symbol", read_only=True)
    class Meta:
        model=Order; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class OpenPositionSerializer(serializers.ModelSerializer):
    symbol_name = serializers.CharField(source="symbol.symbol", read_only=True)
    class Meta:
        model=OpenPosition; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class ClosedTradeSerializer(serializers.ModelSerializer):
    symbol_name = serializers.CharField(source="symbol.symbol", read_only=True)
    class Meta:
        model=ClosedTrade; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
class TradeJournalSerializer(serializers.ModelSerializer):
    class Meta:
        model=TradeJournal; fields="__all__"; read_only_fields=("uuid","created_at","updated_at")
