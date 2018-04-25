from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError

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

from django import forms

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


class TransactionActionAdminForm(forms.ModelForm):
    class Meta:
        model = TransactionAction
        fields = '__all__'

    def clean(self):
        cleaned_data = super(TransactionActionAdminForm, self).clean()
        tr = cleaned_data['transaction']

        transaction_num = len(
            TransactionAction.objects.filter(transaction=tr)
        )

        # validating if admin created a new transaction instead of
        # editing existing one
        if transaction_num > 0:

            error_msg = 'Missing TransactionAction type=pending. Please add \
TransactionAction instead of changing existing one!'

            raise ValidationError(error_msg)

        else:
            return self.cleaned_data


@admin.register(TransactionAction)
class TransactionActionAdmin(admin.ModelAdmin):
    form = TransactionActionAdminForm
