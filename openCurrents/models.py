from __future__ import unicode_literals
from django.contrib.auth.models import User
from uuid import uuid4

from django.db import models

def one_week_from_now():
    return timezone.now() + timedelta(days=7)

class Account(models.Model):
    user = models.OneToOneField(User)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # created / updated timestamps
    date_created = models.DateTimeField('date created', auto_now_add=True)
    date_updated = models.DateTimeField('date last updated', auto_now=True)

    def __unicode__(self):
        return ' '.join([self.user.username, '\'s account'])


# verification tokens
class Token(models.Model):
    email = models.EmailField()
    is_verified = models.BooleanField(default=False)
    token = models.UUIDField(default=uuid4)
    token_type = models.CharField(max_length=20)
    referrer = models.ForeignKey(User, null=True)
    date_expires = models.DateTimeField(
        'date invite token expires',
        default=one_week_from_now
    )

    def __unicode__(self):
        return ' '.join([
            'Verification token for',
            self.email
        ])

# org model
class Org(models.Model):
    name = models.CharField(max_length=100)
    website = models.CharField(max_length=100, unique=True)
    email = models.EmailField(null=True)
    status = models.CharField(max_length=50)
    mission = models.CharField(max_length=4096, null=True)
    reason = models.CharField(max_length=4096, null=True)
    users = models.ManyToManyField(User, through='OrgUser')

    def __unicode__(self):
        return ' '.join([
            str(self.status),
            str(self.name)
        ])


# user-org affiliations
class OrgUser(models.Model):
    user = models.ForeignKey(User)
    org = models.ForeignKey(Org)
    affiliation = models.CharField(max_length=50)

    class Meta:
        unique_together = ('user', 'org')

    def __unicode__(self):
        return ' '.join([
            'User',
            self.user.email,
            'is',
            str(self.affiliation),
            'at',
            self.org.name
        ])
