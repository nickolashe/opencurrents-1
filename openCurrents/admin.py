from django.contrib import admin

# Register your models here.
from openCurrents.models import Account, Org, OrgUser, Token, Project, Event, UserEventRegistration

admin.site.register(Account)
admin.site.register(Org)
admin.site.register(OrgUser)
admin.site.register(Token)
admin.site.register(Project)
admin.site.register(Event)
admin.site.register(UserEventRegistration)
