"""
SMS Service using Arkesel API for FlexiFone notifications
"""
import requests
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class ArkeselSMSService:
    """SMS service using Arkesel API"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'ARKESEL_API_KEY', '')
        self.sender_id = getattr(settings, 'ARKESEL_SENDER_ID', 'FlexiFone')
        self.base_url = 'https://sms.arkesel.com/api/v2/sms/send'
    
    def send_sms(self, phone_number, message):
        """
        Send SMS using Arkesel API
        
        Args:
            phone_number (str): Phone number in international format (e.g., +233XXXXXXXXX)
            message (str): SMS message content
            
        Returns:
            dict: Response from API with success status
        """
        if not self.api_key:
            logger.error("Arkesel API key not configured")
            return {'success': False, 'error': 'API key not configured'}
        
        # Clean phone number (remove spaces, ensure proper format)
        phone_number = self.clean_phone_number(phone_number)
        
        payload = {
            'api_key': self.api_key,
            'to': phone_number,
            'from': self.sender_id,
            'sms': message,
            'type': 'plain',
            'scheduled_date': '',
            'sandbox': getattr(settings, 'ARKESEL_SANDBOX', False)
        }
        
        try:
            response = requests.post(self.base_url, json=payload, timeout=30)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('code') == '200':
                logger.info(f"SMS sent successfully to {phone_number}")
                return {
                    'success': True,
                    'message_id': response_data.get('data', {}).get('id'),
                    'response': response_data
                }
            else:
                logger.error(f"SMS failed to {phone_number}: {response_data}")
                return {
                    'success': False,
                    'error': response_data.get('message', 'Unknown error'),
                    'response': response_data
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"SMS request failed to {phone_number}: {str(e)}")
            return {
                'success': False,
                'error': f'Request failed: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {phone_number}: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def clean_phone_number(self, phone_number):
        """
        Clean and format phone number for Ghana
        
        Args:
            phone_number (str): Raw phone number
            
        Returns:
            str: Cleaned phone number in international format
        """
        if not phone_number:
            return ''
        
        # Remove all non-digit characters
        digits_only = ''.join(filter(str.isdigit, phone_number))
        
        # Handle different formats
        if digits_only.startswith('233'):
            # Already in international format without +
            return f"+{digits_only}"
        elif digits_only.startswith('0'):
            # Local format (0XXXXXXXXX) - convert to international
            return f"+233{digits_only[1:]}"
        elif len(digits_only) == 9:
            # 9 digits without leading 0 - add Ghana country code
            return f"+233{digits_only}"
        else:
            # Return as is with + if not already present
            return f"+{digits_only}" if not phone_number.startswith('+') else phone_number
    
    def send_pickup_ready_notification(self, credit_account):
        """
        Send SMS notification when device is ready for pickup
        
        Args:
            credit_account: CreditAccount instance
            
        Returns:
            dict: SMS sending result
        """
        if not credit_account.user.username:  # Assuming phone is stored in username or add phone field
            return {'success': False, 'error': 'No phone number available'}
        
        phone_name = credit_account.phone.name if credit_account.phone else "your device"
        
        message = f"""🎉 Great news! Your {phone_name} is ready for pickup!

📍 Location: {credit_account.pickup_location}
📅 Hours: Mon-Sat, 9AM-6PM
📞 Call: +233 XX XXX XXXX

Bring: Valid ID & this message

- FlexiFone Team"""
        
        # Assuming phone number is stored in user profile or username
        # You may need to adjust this based on your User model
        phone_number = getattr(credit_account.user, 'phone_number', credit_account.user.username)
        
        result = self.send_sms(phone_number, message)
        
        if result['success']:
            # Update the account with SMS sent timestamp
            credit_account.sms_sent_at = timezone.now()
            credit_account.save()
        
        return result
    
    def send_plan_completed_notification(self, credit_account):
        """
        Send SMS notification when plan is completed
        
        Args:
            credit_account: CreditAccount instance
            
        Returns:
            dict: SMS sending result
        """
        phone_name = credit_account.phone.name if credit_account.phone else "your device"
        
        message = f"""🎉 Congratulations! Your FlexiFone plan for {phone_name} is complete!

Your device will be prepared for pickup. You'll receive another message when it's ready.

Thank you for choosing FlexiFone!

- FlexiFone Team"""
        
        phone_number = getattr(credit_account.user, 'phone_number', credit_account.user.username)
        return self.send_sms(phone_number, message)

# Global instance
sms_service = ArkeselSMSService()

def send_pickup_ready_sms(credit_account):
    """Convenience function to send pickup ready SMS"""
    return sms_service.send_pickup_ready_notification(credit_account)

def send_plan_completed_sms(credit_account):
    """Convenience function to send plan completed SMS"""
    return sms_service.send_plan_completed_notification(credit_account)
