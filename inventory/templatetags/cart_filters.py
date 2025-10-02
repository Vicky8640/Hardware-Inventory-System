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



@register.filter
def get_item_sale_price(data, asset_pk):
    """
    Looks up the sale price for a given asset PK from the POST data (which is a dict-like object).
    Returns a Decimal.
    """
    price_key = f'sale_price_{asset_pk}'
    price_str = data.get(price_key)
    
    if price_str:
        try:
            return Decimal(price_str)
        except:
            pass
    return None

@register.filter
def length(value):
    """
    Returns the length of a list, used for request.session.mixed_sale_assets|length.
    """
    try:
        return len(value)
    except:
        return 0

# And don't forget the current_query tag from the previous response!
# @register.simple_tag(takes_context=True)
# def current_query(context):
#     ...
# inventory/templatetags/inventory_extras.py


@register.filter
def current_query(request):
    """
    Returns the current GET query string, excluding the 'page' parameter.
    Used for maintaining filters across pagination clicks.
    """
    if not request:
        return ""
        
    # Get a mutable copy of the query parameters
    params = request.GET.copy()
    
    # Remove the 'page' parameter
    if 'page' in params:
        del params['page']
        
    # Encode the remaining parameters and prepend '&' if they exist
    if params:
        return '&' + params.urlencode()
    else:
        return ''