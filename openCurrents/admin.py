from django.contrib import admin

# Register your models here.
from openCurrents.models import \
    Org, \
    OrgUser, \
    Token, \
    Project, \
    Event, \
    UserEventRegistration, \
    UserSettings, \
    UserTimeLog, \
    AdminActionUserTime, \
    Offer, \
    Transaction, \
    Item, \
    TransactionAction, \
    Entity, \
    UserEntity, \
    OrgEntity, \
    Ledger

admin.site.register(Org)
admin.site.register(OrgUser)
admin.site.register(Token)
admin.site.register(Project)
admin.site.register(Event)
admin.site.register(UserEventRegistration)
admin.site.register(UserSettings)
admin.site.register(UserTimeLog)
admin.site.register(AdminActionUserTime)
admin.site.register(Offer)
admin.site.register(Transaction)
admin.site.register(Item)
admin.site.register(TransactionAction)
admin.site.register(Entity)
admin.site.register(UserEntity)
admin.site.register(OrgEntity)
admin.site.register(Ledger)
