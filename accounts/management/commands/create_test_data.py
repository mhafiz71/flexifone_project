from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Product, CreditAccount
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test data for the FlexiFone application'

    def handle(self, *args, **options):
        self.stdout.write('Creating test data...')

        # Create test user if it doesn't exist
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={
                'email': 'test@example.com',
                'first_name': 'Test',
                'last_name': 'User',
                'national_id': '123456789',
                'credit_score': 700,
                'monthly_income': Decimal('3000.00'),
                'is_verified': True,
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(self.style.SUCCESS(
                'Created test user: testuser (password: testpass123)'))
        else:
            self.stdout.write('Test user already exists')

        # Create test products if they don't exist
        products_data = [
            {
                'name': 'iPhone 15 Pro',
                'brand': 'APPLE',
                'description': 'Latest iPhone with advanced features',
                'price': Decimal('999.00'),
                'stock_quantity': 10,
                'credit_available': True,
                'min_credit_score': 600,
                'max_installments': 12,
                'interest_rate': Decimal('5.99'),
            },
            {
                'name': 'Samsung Galaxy S24',
                'brand': 'SAMSUNG',
                'description': 'Premium Android smartphone',
                'price': Decimal('899.00'),
                'stock_quantity': 15,
                'credit_available': True,
                'min_credit_score': 600,
                'max_installments': 12,
                'interest_rate': Decimal('5.99'),
            },
            {
                'name': 'Google Pixel 8',
                'brand': 'GOOGLE',
                'description': 'Google\'s flagship phone with AI features',
                'price': Decimal('699.00'),
                'stock_quantity': 8,
                'credit_available': True,
                'min_credit_score': 600,
                'max_installments': 12,
                'interest_rate': Decimal('5.99'),
            },
        ]

        for product_data in products_data:
            product, created = Product.objects.get_or_create(
                name=product_data['name'],
                defaults=product_data
            )
            if created:
                self.stdout.write(f'Created product: {product.name}')
            else:
                self.stdout.write(f'Product already exists: {product.name}')

        # Create a test credit account for the user
        if not hasattr(user, 'credit_account'):
            product = Product.objects.first()
            account = CreditAccount.objects.create(
                user=user,
                product=product,
                account_type=CreditAccount.AccountType.SAVINGS,
                status=CreditAccount.Status.ACTIVE,
                balance=Decimal('0.00'),
            )
            self.stdout.write(
                f'Created test credit account for {user.username}')

        self.stdout.write(self.style.SUCCESS(
            'Test data created successfully!'))
        self.stdout.write('You can now login with:')
        self.stdout.write('Username: testuser')
        self.stdout.write('Password: testpass123')
