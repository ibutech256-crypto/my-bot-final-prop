from django.contrib import admin
from backend.apps.analytics_app import models
for n in dir(models):
    o=getattr(models,n)
    if hasattr(o,"_meta") and getattr(o._meta,"app_label",None)=="analytics_app":
        try: admin.site.register(o)
        except admin.sites.AlreadyRegistered: pass
