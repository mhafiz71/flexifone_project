from django import template

register = template.Library()

@register.filter
def is_completed_status(status):
    """Check if account status is in completed states"""
    return status in ['COMPLETED', 'DELIVERED', 'PICKED_UP']
