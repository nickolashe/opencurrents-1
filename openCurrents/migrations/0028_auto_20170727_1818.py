# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-27 18:18
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0027_auto_20170720_1739'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='creator_id',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='event',
            name='notified',
            field=models.BooleanField(default=False),
        ),
    ]
