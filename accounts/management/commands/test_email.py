from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


class Command(BaseCommand):
    help = 'Test email sending functionality with Gmail SMTP'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            default='abdulnasirmhafiz567@gmail.com',
            help='Email address to send test email to'
        )
        parser.add_argument(
            '--template',
            type=str,
            default='welcome_email',
            help='Email template to test (welcome_email, credit_verified, plan_completed)'
        )

    def handle(self, *args, **options):
        recipient_email = options['to']
        template_name = options['template']
        
        self.stdout.write(f"Testing email sending to: {recipient_email}")
        self.stdout.write(f"Using template: {template_name}")
        self.stdout.write(f"SMTP Host: {settings.EMAIL_HOST}")
        self.stdout.write(f"SMTP User: {settings.EMAIL_HOST_USER}")
        
        try:
            # Create test context based on template
            if template_name == 'welcome_email':
                context = {
                    'user': {'first_name': 'Test', 'username': 'testuser'},
                    'account': {
                        'phone': {'name': 'iPhone 15', 'price': '5000'},
                        'account_type': 'CREDIT',
                        'installment_amount': '500',
                        'next_payment_due_date': None
                    }
                }
                subject = "Welcome to FlexiFone - Test Email"
            elif template_name == 'credit_verified':
                context = {
                    'user': {'first_name': 'Test', 'username': 'testuser'},
                    'application': {
                        'phone': {'name': 'iPhone 15', 'price': '5000'},
                        'requested_loan_amount': '4500',
                        'requested_installment_count': 12
                    }
                }
                subject = "Credit Application Verified - Test Email"
            elif template_name == 'plan_completed':
                context = {
                    'user': {'first_name': 'Test', 'username': 'testuser'},
                    'account': {
                        'phone': {'name': 'iPhone 15'},
                        'pickup_location': 'FlexiFone Store, Accra',
                        'pickup_instructions': 'Please bring valid ID'
                    }
                }
                subject = "Plan Completed - Test Email"
            else:
                self.stdout.write(self.style.ERROR(f"Unknown template: {template_name}"))
                return
            
            # Render HTML template
            html_content = render_to_string(f'emails/{template_name}.html', context)
            
            # Try to render text template as fallback
            try:
                text_content = render_to_string(f'emails/{template_name}.txt', context)
            except:
                text_content = f"Please view this email in an HTML-capable email client.\n\nSubject: {subject}"
            
            # Use EMAIL_FROM if available, otherwise DEFAULT_FROM_EMAIL
            from_email = getattr(settings, 'EMAIL_FROM', settings.DEFAULT_FROM_EMAIL)
            
            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[recipient_email]
            )
            email.attach_alternative(html_content, "text/html")
            
            # Send email
            email.send()
            
            self.stdout.write(
                self.style.SUCCESS(f"✅ Test email sent successfully!")
            )
            self.stdout.write(f"   📧 To: {recipient_email}")
            self.stdout.write(f"   📝 Subject: {subject}")
            self.stdout.write(f"   📤 From: {from_email}")
            self.stdout.write(f"   🎨 Template: {template_name}.html")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Failed to send test email: {e}")
            )
            self.stdout.write(f"Error details: {str(e)}")
