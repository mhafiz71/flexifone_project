# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Product, CreditAccount, Transaction
from django.utils.html import format_html


@admin.action(description='Mark selected users as Verified')
def make_verified(modeladmin, request, queryset):
    queryset.update(is_verified=True)


class CustomUserAdmin(UserAdmin):
    model = User
    # Add is_verified to display and fieldsets
    list_display = ('username', 'email', 'is_verified',
                    'is_staff', 'national_id')
    list_filter = ('is_verified', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('national_id', 'is_verified')}),
    )
    # --- ADD THE ACTION ---
    actions = [make_verified]


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ('amount', 'timestamp', 'transaction_id')


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'balance', 'remaining_balance',
                    'progress_percentage', 'status', 'accepted_terms')  # Add progress_percentage
    list_filter = ('status', 'product', 'accepted_terms')
    search_fields = ('user__username', 'user__email', 'user__national_id')
    inlines = [TransactionInline]
    # Add it here too for the detail view
    readonly_fields = ('balance', 'remaining_balance',
                       'progress_percentage', 'accepted_at')

    @admin.display(ordering='status', description='Status')
    def colored_status(self, obj):
        if obj.status == 'OVERDUE':
            color = 'red'
        elif obj.status in ['PAID_OFF', 'COMPLETED']:
            color = 'green'
        elif obj.status in ['REPAYING', 'ACTIVE']:
            color = 'blue'
        else:
            color = 'black'
        return format_html('<b style="color: {};">{}</b>', color, obj.get_status_display())

    # This makes the progress_percentage column sortable in the admin
    def progress_percentage(self, obj):
        return f"{obj.progress_percentage}%"
    progress_percentage.short_description = 'Progress'


admin.site.register(User, CustomUserAdmin)
admin.site.register(Product)
admin.site.register(Transaction)
