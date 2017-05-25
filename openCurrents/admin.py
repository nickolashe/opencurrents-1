from django.contrib import admin

# Register your models here.
from openCurrents.models import Account, Org, OrgUser, Token, Project

admin.site.register(Account)
admin.site.register(Org)
admin.site.register(OrgUser)
admin.site.register(Token)
admin.site.register(Project)
