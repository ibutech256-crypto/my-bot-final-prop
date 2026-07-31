import os, inspect
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
import django; django.setup()
from backend.apps.trading import views

# Get the SignalViewSet source
src = inspect.getsource(views.SignalViewSet.get_queryset)
print("SignalViewSet.get_queryset:")
print(src[:500])

# Test what it returns
qs = views.SignalViewSet().get_queryset()
print(f"\nQuery returns: {qs.count()} signals")
print(f"\nQuery SQL: {qs.query}")

