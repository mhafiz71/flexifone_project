from django import template

register = template.Library()

@register.filter
def phone_display(phone):
    """
    Display phone brand and name in a user-friendly format.
    Handles cases where phone is None or has empty fields.
    """
    if not phone:
        return "Unknown Phone"
    
    brand = phone.get_brand_display() if hasattr(phone, 'get_brand_display') else "Unknown Brand"
    name = phone.name if phone.name else "Phone"
    
    return f"{brand} {name}"

@register.filter
def phone_name_or_default(phone, default="Phone"):
    """
    Get phone name or return default if empty/None
    """
    if not phone or not phone.name:
        return default
    return phone.name

@register.filter
def phone_brand_or_default(phone, default="Unknown Brand"):
    """
    Get phone brand display or return default if empty/None
    """
    if not phone:
        return default
    return phone.get_brand_display() if hasattr(phone, 'get_brand_display') else default
