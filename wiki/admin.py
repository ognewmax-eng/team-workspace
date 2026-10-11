"""
Админ-панель для вики.
"""
from django.contrib import admin
from .models import WikiArticle, WikiArticleFile


@admin.register(WikiArticle)
class WikiArticleAdmin(admin.ModelAdmin):
    list_select_related = ['department', 'author', 'updated_by']
    list_per_page = 30
    list_display = ['title', 'category', 'department', 'author', 'is_pinned', 'views_count', 'created_at', 'updated_at']
    list_filter = ['category', 'department', 'is_pinned', 'created_at']
    search_fields = ['title', 'content', 'tags']
    readonly_fields = ['created_at', 'updated_at', 'views_count']
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'content', 'category', 'tags')
        }),
        ('Доступ', {
            'fields': ('department', 'is_pinned')
        }),
        ('Авторство', {
            'fields': ('author', 'updated_by')
        }),
        ('Статистика', {
            'fields': ('views_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # При создании
            obj.author = request.user
        else:  # При обновлении
            from .workspace import snapshot
            previous = WikiArticle.objects.get(pk=obj.pk)
            snapshot(previous, request.user)
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(WikiArticleFile)
class WikiArticleFileAdmin(admin.ModelAdmin):
    list_select_related = ['article', 'uploaded_by']
    list_display = ['article', 'file', 'uploaded_by', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['article__title', 'description']
    readonly_fields = ['uploaded_at']
