from django.contrib import admin

# Register your models here.
from openCurrents.models import Account, \
    Org, \
    OrgUser, \
    Token, \
    Project, \
    Event, \
    UserEventRegistration, \
    UserTimeLog, \
    AdminActionUserTime, \
    Offer, \
    Transaction, \
    UserOfferAction

admin.site.register(Account)
admin.site.register(Org)
admin.site.register(OrgUser)
admin.site.register(Token)
admin.site.register(Project)
admin.site.register(Event)
admin.site.register(Offer)
admin.site.register(UserOfferAction)
admin.site.register(Transaction)
admin.site.register(UserEventRegistration)
admin.site.register(UserTimeLog)
admin.site.register(AdminActionUserTime)
