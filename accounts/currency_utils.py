"""
Currency conversion utilities for FlexiFone
"""
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings


def ghs_to_usd(ghs_amount):
    """
    Convert Ghana Cedis to USD for Stripe processing
    
    Args:
        ghs_amount (Decimal or float): Amount in GHS
        
    Returns:
        Decimal: Amount in USD
    """
    if not ghs_amount:
        return Decimal('0.00')
    
    ghs_decimal = Decimal(str(ghs_amount))
    usd_rate = Decimal(str(settings.USD_TO_GHS_RATE))
    
    # Convert GHS to USD: GHS / exchange_rate = USD
    usd_amount = ghs_decimal / usd_rate
    
    # Round to 2 decimal places
    return usd_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def usd_to_ghs(usd_amount):
    """
    Convert USD back to Ghana Cedis for display
    
    Args:
        usd_amount (Decimal or float): Amount in USD
        
    Returns:
        Decimal: Amount in GHS
    """
    if not usd_amount:
        return Decimal('0.00')
    
    usd_decimal = Decimal(str(usd_amount))
    usd_rate = Decimal(str(settings.USD_TO_GHS_RATE))
    
    # Convert USD to GHS: USD * exchange_rate = GHS
    ghs_amount = usd_decimal * usd_rate
    
    # Round to 2 decimal places
    return ghs_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def ghs_to_usd_cents(ghs_amount):
    """
    Convert Ghana Cedis to USD cents for Stripe (Stripe uses smallest currency unit)
    
    Args:
        ghs_amount (Decimal or float): Amount in GHS
        
    Returns:
        int: Amount in USD cents
    """
    usd_amount = ghs_to_usd(ghs_amount)
    # Convert to cents (multiply by 100)
    return int(usd_amount * 100)


def usd_cents_to_ghs(usd_cents):
    """
    Convert USD cents back to Ghana Cedis
    
    Args:
        usd_cents (int): Amount in USD cents
        
    Returns:
        Decimal: Amount in GHS
    """
    if not usd_cents:
        return Decimal('0.00')
    
    # Convert cents to USD dollars
    usd_amount = Decimal(str(usd_cents)) / 100
    
    # Convert USD to GHS
    return usd_to_ghs(usd_amount)


def format_ghs_amount(amount):
    """
    Format amount for display in GHS
    
    Args:
        amount (Decimal or float): Amount in GHS
        
    Returns:
        str: Formatted amount with currency symbol
    """
    if not amount:
        return f"{settings.DISPLAY_CURRENCY_SYMBOL}0.00"
    
    amount_decimal = Decimal(str(amount))
    return f"{settings.DISPLAY_CURRENCY_SYMBOL}{amount_decimal:.2f}"


def format_usd_amount(amount):
    """
    Format amount for display in USD
    
    Args:
        amount (Decimal or float): Amount in USD
        
    Returns:
        str: Formatted amount with currency symbol
    """
    if not amount:
        return f"{settings.STRIPE_CURRENCY_SYMBOL}0.00"
    
    amount_decimal = Decimal(str(amount))
    return f"{settings.STRIPE_CURRENCY_SYMBOL}{amount_decimal:.2f}"
