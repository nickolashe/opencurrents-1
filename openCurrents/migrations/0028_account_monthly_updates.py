# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-07-26 15:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0027_auto_20170720_1739'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='monthly_updates',
            field=models.BooleanField(default=False),
        ),
    ]