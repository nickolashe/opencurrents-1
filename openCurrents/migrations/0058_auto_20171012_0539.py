# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-10-12 05:39
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0057_auto_20171012_0535'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='UserOfferAction',
            new_name='TransactionAction',
        ),
    ]