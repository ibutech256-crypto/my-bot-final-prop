from rest_framework.viewsets import ModelViewSet
class ActiveModelViewSet(ModelViewSet):
    lookup_field="uuid"
    def get_queryset(self):
        qs=super().get_queryset(); return qs.filter(is_deleted=False) if hasattr(qs.model,"is_deleted") else qs
    def perform_destroy(self,instance):
        instance.soft_delete() if hasattr(instance,"soft_delete") else super().perform_destroy(instance)
