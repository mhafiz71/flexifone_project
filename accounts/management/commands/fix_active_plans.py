"""
Management command to fix is_active_plan field for existing accounts
"""
from django.core.management.base import BaseCommand
from accounts.models import CreditAccount


class Command(BaseCommand):
    help = 'Fix is_active_plan field for existing accounts based on their status'

    def handle(self, *args, **options):
        self.stdout.write('Fixing is_active_plan field for existing accounts...')
        
        # Get all accounts
        accounts = CreditAccount.objects.all()
        fixed_count = 0
        
        for account in accounts:
            old_is_active = getattr(account, 'is_active_plan', True)
            
            # Determine correct is_active_plan value based on status
            inactive_statuses = [
                CreditAccount.Status.PICKED_UP,
                CreditAccount.Status.CLOSED,
                CreditAccount.Status.DECLINED,
                CreditAccount.Status.COMPLETED,
                CreditAccount.Status.AVAILABLE_FOR_PICKUP
            ]
            
            should_be_active = account.status not in inactive_statuses
            
            # Update if different
            if old_is_active != should_be_active:
                account.is_active_plan = should_be_active
                account.save()
                fixed_count += 1
                
                self.stdout.write(
                    f'Fixed account {account.id} (user: {account.user.username}) - '
                    f'Status: {account.status}, Active: {old_is_active} -> {should_be_active}'
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully fixed {fixed_count} accounts out of {accounts.count()} total accounts'
            )
        )
