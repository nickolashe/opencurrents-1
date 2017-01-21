from django.contrib import admin

# Register your models here.
from openCurrents.models import Account, Token

admin.site.register(Account)
admin.site.register(Token)
