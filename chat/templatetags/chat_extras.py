from django import template

register = template.Library()

@register.filter
def get_partner(conversation, current_user):
    return conversation.get_other_user(current_user)

@register.filter
def get_last_message(conversation, user):
    return conversation.get_last_visible_message(user)
