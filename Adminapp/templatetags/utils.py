from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.simple_tag
def rate_key(location_id, item_id):
    return f"{location_id}_{item_id}"