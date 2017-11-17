# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-07 23:02
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0066_auto_20171107_2003'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='price_actual',
            field=models.DecimalField(decimal_places=2, default=1, max_digits=10),
            preserve_default=False,
        ),
    ]
