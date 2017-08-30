# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-08-15 03:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0043_auto_20170809_0425'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='orguser',
            options={'permissions': (('admin', 'User is org admin'),)},
        ),
        migrations.AddField(
            model_name='orguser',
            name='approved',
            field=models.BooleanField(default=False),
        ),
    ]