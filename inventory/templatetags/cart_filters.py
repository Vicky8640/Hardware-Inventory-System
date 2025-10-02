# inventory/templatetags/inventory_extras.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Allows dictionary/QueryDict access by key in Django templates.
    Used here to preserve user input on validation error.
    """
    return dictionary.get(key)



# inventory/templatetags/inventory_extras.py

@register.simple_tag(takes_context=True)
def current_query(context):
    """
    Returns the current GET query string, excluding the 'page' parameter.
    Used to preserve filters when paginating.
    """
    request = context['request']
    query_params = request.GET.copy()
    
    # Remove 'page' from the query parameters
    if 'page' in query_params:
        del query_params['page']
        
    # Prepend '&' if there are remaining parameters
    if query_params:
        return f"&{query_params.urlencode()}"
    return ""