from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'department', 'uploaded_by', 'created_at']
    list_filter = ['category', 'department', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['uploaded_by', 'created_at']
    date_hierarchy = 'created_at'
    list_select_related = ['department', 'uploaded_by']
    list_per_page = 30

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
