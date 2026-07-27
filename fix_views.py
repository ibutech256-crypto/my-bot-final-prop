"""Fix OpenPositionViewSet to filter is_deleted=False."""
import os, sys, signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

views_path = r"C:\prop-frim-bot\backend\apps\trading\views.py"
with open(views_path, "r") as f:
    content = f.read()

# Fix the OpenPositionViewSet queryset
old = "class OpenPositionViewSet(ActiveModelViewSet): queryset=OpenPosition.objects.all(); serializer_class=serializers.OpenPositionSerializer; permission_classes=[ReadOnlyOrPrivileged]"
new = "class OpenPositionViewSet(ActiveModelViewSet): queryset=OpenPosition.objects.filter(is_deleted=False); serializer_class=serializers.OpenPositionSerializer; permission_classes=[ReadOnlyOrPrivileged]"

if old in content:
    content = content.replace(old, new)
    open(views_path, "w").write(content)
    print("✅ OpenPositionViewSet fixed: now filters is_deleted=False")
else:
    print("Pattern not found - checking actual content:")
    idx = content.find("OpenPositionViewSet")
    if idx >= 0:
        print(f"Found at {idx}: {content[idx:idx+200]}")

# Check that ActiveModelViewSet filters is_deleted by default
common_models_path = r"C:\prop-frim-bot\backend\apps\common\models.py"
if os.path.exists(common_models_path):
    with open(common_models_path, "r") as f:
        cm = f.read()
    if "ActiveModelViewSet" in cm:
        idx = cm.find("class ActiveModelViewSet")
        end = cm.find("\nclass ", idx+1)
        print(f"\nActiveModelViewSet def:\n{cm[idx:end][:500]}")
