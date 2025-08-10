from django.contrib import admin
from .models import Phone

@admin.register(Phone)
class PhoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'price', 'stock', 'is_active', 'created_at')
    list_filter = ('brand', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('brand', 'name')}
    list_editable = ('price', 'stock', 'is_active')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'brand', 'price', 'description')
        }),
        ('Specifications', {
            'fields': ('specifications', 'image')
        }),
        ('Inventory', {
            'fields': ('stock', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
