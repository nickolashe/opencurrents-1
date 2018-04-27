from django.contrib import admin
from django.core.exceptions import ValidationError
from import_export.admin import ImportExportModelAdmin
from import_export import resources

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
    Ledger
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


class LedgerResource(resources.ModelResource):
    class Meta:
        model = Ledger


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


class TransactionAdmin(ImportExportModelAdmin):
    resource_class = TransactionResource
    search_fields = (
        'user__id', 'user__email', 'offer__id', 'offer__org__name', 'biz_name'
    )


class UserCashOutResource(resources.ModelResource):
    class Meta:
        model = UserCashOut


class UserCashOutAdmin(ImportExportModelAdmin):
    resource_class = UserCashOutResource
    search_fields = ('user__email',)


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
admin.site.register(UserEventRegistration)
admin.site.register(UserSettings)
admin.site.register(UserTimeLog, UserTimeLogAdmin)
admin.site.register(AdminActionUserTime, AdminActionUserTimeAdmin)
admin.site.register(Offer)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Item)
admin.site.register(TransactionAction)
admin.site.register(Entity)
admin.site.register(UserEntity)
admin.site.register(OrgEntity)
admin.site.register(Ledger, LedgerAdmin)
