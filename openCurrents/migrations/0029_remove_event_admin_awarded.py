# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-25 22:48
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0028_event_admin_awarded'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='event',
            name='admin_awarded',
        ),
    ]
