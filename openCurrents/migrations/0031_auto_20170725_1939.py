# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-07-25 19:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0030_auto_20170725_1500'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='is_public',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='usertimelog',
            name='datetime_duration',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=12),
        ),
    ]
