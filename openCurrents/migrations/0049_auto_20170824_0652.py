# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-08-24 06:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0048_auto_20170824_0651'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adminactionusertime',
            name='action_type',
            field=models.CharField(choices=[('app', 'approved'), ('def', 'deferred'), ('dec', 'declined')], max_length=3),
        ),
    ]