from django.urls import include,path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView,TokenVerifyView
from backend.apps.accounts.views import UserViewSet,AccountViewSet,SessionRecordViewSet
from backend.apps.trading.views import BrokerProfileViewSet,BrokerSettingViewSet,TradingAccountViewSet,TradingSymbolViewSet,WatchlistViewSet,SignalViewSet,OrderViewSet,OpenPositionViewSet,ClosedTradeViewSet,TradeJournalViewSet
from backend.apps.risk.views import RiskProfileViewSet
from backend.apps.analytics_app.views import PerformanceAnalyticsViewSet,StrategyStatisticViewSet,AIAnalysisViewSet
from backend.apps.notifications.views import NotificationViewSet,TelegramSubscriberViewSet
from backend.apps.subscriptions.views import SubscriptionPlanViewSet,SubscriptionViewSet,InvoiceViewSet,PaymentViewSet,RefundViewSet,ReferralViewSet
from backend.apps.system.views import SystemLogViewSet,AuditLogViewSet,ErrorLogViewSet
from backend.apps.intelligence_app.views import IntelligenceDecisionLogViewSet,SymbolIntelligenceSnapshotViewSet,OperationalIncidentViewSet,CommercialLicenseRecordViewSet
router=DefaultRouter()
for prefix,viewset in [("users",UserViewSet),("accounts",AccountViewSet),("sessions",SessionRecordViewSet),("brokers",BrokerProfileViewSet),("broker-settings",BrokerSettingViewSet),("trading-accounts",TradingAccountViewSet),("symbols",TradingSymbolViewSet),("watchlists",WatchlistViewSet),("signals",SignalViewSet),("orders",OrderViewSet),("open-positions",OpenPositionViewSet),("closed-trades",ClosedTradeViewSet),("journal",TradeJournalViewSet),("risk-profiles",RiskProfileViewSet),("performance",PerformanceAnalyticsViewSet),("strategy-statistics",StrategyStatisticViewSet),("ai-analysis",AIAnalysisViewSet),("notifications",NotificationViewSet),("telegram-subscribers",TelegramSubscriberViewSet),("plans",SubscriptionPlanViewSet),("subscriptions",SubscriptionViewSet),("invoices",InvoiceViewSet),("payments",PaymentViewSet),("refunds",RefundViewSet),("referrals",ReferralViewSet),("system-logs",SystemLogViewSet),("audit-logs",AuditLogViewSet),("error-logs",ErrorLogViewSet),("intelligence-decisions",IntelligenceDecisionLogViewSet),("symbol-intelligence",SymbolIntelligenceSnapshotViewSet),("operational-incidents",OperationalIncidentViewSet),("commercial-licenses",CommercialLicenseRecordViewSet)]: router.register(prefix,viewset,basename=prefix)
urlpatterns=[path("auth/token/",TokenObtainPairView.as_view()),path("auth/token/refresh/",TokenRefreshView.as_view()),path("auth/token/verify/",TokenVerifyView.as_view()),path("",include(router.urls))]
