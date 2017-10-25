# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-10-16 08:00
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0058_auto_20171012_0539'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transactionaction',
            name='action_type',
            field=models.CharField(choices=[('req', 'pending'), ('app', 'approved'), ('red', 'redeemed'), ('dec', 'declined')], default='req', max_length=7),
        ),
    ]