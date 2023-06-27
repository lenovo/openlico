from django import template

register = template.Library()


@register.filter
def user_bill_group_name(users_bill_group, username):
    bill_group_name = ''
    for user_bill_group in users_bill_group:
        if user_bill_group.username and user_bill_group.username == username:
            bill_group_name = user_bill_group.bill_group_name
            break

    return bill_group_name
