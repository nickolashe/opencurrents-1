from django.contrib import admin
from django.core.exceptions import ValidationError
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from django_admin_listfilter_dropdown.filters import DropdownFilter, RelatedDropdownFilter

from openCurrents.models import (
    Org,
    OrgUser,
    Token,
    Project,
    Event,
    UserCashOut,
    UserEventRegistration,
    UserSettings,
    UserTimeLog,
    AdminActionUserTime,
    Offer,
    Transaction,
    Item,
    TransactionAction,
    Entity,
    UserEntity,
    OrgEntity,
    Ledger,
    GiftCardInventory
)

from django import forms


class AdminActionUserTimeResource(resources.ModelResource):
    class Meta:
        model = AdminActionUserTime


class AdminActionUserTimeAdmin(ImportExportModelAdmin):
    resource_class = AdminActionUserTimeResource
    search_fields = (
        'user__email',
        'usertimelog__user__email',
        'usertimelog__event__project__org__name'
    )


class EventAdmin(admin.ModelAdmin):
    class Meta:
        model = Event

    list_filter = (
        ('location', DropdownFilter)
    )


class LedgerResource(resources.ModelResource):
    class Meta:
        model = Ledger
        fields = (
            'id',
            'entity_from',
            'entity_to',
            'currency',
            'amount',
            'is_issued',
            'is_bonus',
            'transaction__id',
            'action__user__id',
            'date_created'
        )
        export_order = fields

    def dehydrate_entity_from(self, ledger):
        try:
            return ledger.entity_from.userentity.user.email
        except:
            return ledger.entity_from.orgentity.org.name

    def dehydrate_entity_to(self, ledger):
        try:
            return ledger.entity_to.userentity.user.email
        except:
            return ledger.entity_to.orgentity.org.name


class LedgerAdmin(ImportExportModelAdmin):
    resource_class = LedgerResource
    # search_fields = ('entity_to__org__email',)


class OrgResource(resources.ModelResource):
    class Meta:
        model = Org


class OrgAdmin(ImportExportModelAdmin):
    resource_class = OrgResource
    search_fields = ('name',)


class TransactionResource(resources.ModelResource):
    class Meta:
        model = Transaction
        fields = (
            'id',
            'user__id',
            'user__email',
            'offer__id',
            'offer__org__name',
            'price_reported',
            'currents_amount',
            'pop_image',
            'pop_no_proof',
            'pop_type',
            'biz_name',
            'date_created'
        )
        export_order = fields


class TransactionAdmin(ImportExportModelAdmin):
    resource_class = TransactionResource
    search_fields = (
        'user__id', 'user__email', 'offer__id', 'offer__org__name', 'biz_name'
    )


class TransactionActionResource(resources.ModelResource):
    class Meta:
        model = TransactionAction
        fields = (
            'id',
            'transaction__id',
            'transaction__user__id',
            'transaction__user__email',
            'transaction__offer__id',
            'transaction__offer__org__name',
            'action_type',
            'date_created'
        )
        export_order = fields


class TransactionActionAdmin(ImportExportModelAdmin):
    resource_class = TransactionActionResource
    search_fields = (
        'transaction__id',
        'transaction__user__email',
        'transaction__offer__org__name'
    )


class UserCashOutResource(resources.ModelResource):
    class Meta:
        model = UserCashOut


class UserCashOutAdmin(ImportExportModelAdmin):
    resource_class = UserCashOutResource
    search_fields = ('user__email',)


class UserEventRegistrationResource(resources.ModelResource):
    class Meta:
        model = UserEventRegistration


class UserEventRegistrationAdmin(ImportExportModelAdmin):
    resource_class = UserEventRegistrationResource
    search_fields = (
        'user__email',
        'event__id',
        'event__project__name',
        'event__project__org__name',
        'event__location',
        'event__datetime_start'
    )


class UserTimeLogResource(resources.ModelResource):
    class Meta:
        model = UserTimeLog


class UserTimeLogAdmin(ImportExportModelAdmin):
    resource_class = UserTimeLogResource
    search_fields = (
        'user__id',
        'user__email',
        'event__id',
        'event__project__name',
        'event__project__org__name'
    )


admin.site.register(Org, OrgAdmin)
admin.site.register(OrgUser)
admin.site.register(Token)
admin.site.register(Project)
admin.site.register(Event)
admin.site.register(UserCashOut, UserCashOutAdmin)
admin.site.register(UserEventRegistration, UserEventRegistrationAdmin)
admin.site.register(UserSettings)
admin.site.register(UserTimeLog, UserTimeLogAdmin)
admin.site.register(AdminActionUserTime, AdminActionUserTimeAdmin)
admin.site.register(Offer)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Item)
admin.site.register(TransactionAction, TransactionActionAdmin)
admin.site.register(Entity)
admin.site.register(UserEntity)
admin.site.register(OrgEntity)
admin.site.register(Ledger, LedgerAdmin),
admin.site.register(GiftCardInventory)
