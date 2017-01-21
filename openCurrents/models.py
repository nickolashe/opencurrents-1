from __future__ import unicode_literals
from django.contrib.auth.models import User
from uuid import uuid4

from django.db import models

def one_week_from_now():
    return timezone.now() + timedelta(days=7)

class Account(models.Model):
    user = models.OneToOneField(User)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date last updated', auto_now=True)


# verification tokens
class Token(models.Model):
    email = models.EmailField()
    is_verified = models.BooleanField(default=False)
    token = models.UUIDField(default=uuid4)
    token_type = models.CharField(max_length=20)
    date_expires = models.DateTimeField(
        'date invite token expires',
        default=one_week_from_now
    )
