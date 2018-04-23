from django.contrib import admin
from django.contrib import messages

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
# admin.site.register(TransactionAction)
admin.site.register(Entity)
admin.site.register(UserEntity)
admin.site.register(OrgEntity)
admin.site.register(Ledger)


@admin.register(TransactionAction)
class TransactionActionAdmin(admin.ModelAdmin):

    def save_model(self, request, obj, form, change):
        # get model instance
        tr_action = form.instance

        # notify admin if he tries change status to 'pending'
        if tr_action.action_type == 'req':
            messages.add_message(
                request, messages.ERROR,
                'Missing TransactionAction type=pending. Please add \
TransactionAction instead of changing existing one.!'
            )
        super(TransactionActionAdmin, self).save_model(request, obj, form, change)
