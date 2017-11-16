# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-10-23 04:21
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0062_ledger'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ledger',
            name='account_from',
        ),
        migrations.RemoveField(
            model_name='ledger',
            name='account_to',
        ),
        migrations.AddField(
            model_name='ledger',
            name='entity_from',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='transaction_out', to='openCurrents.Entity'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ledger',
            name='entity_to',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='transaction_in', to='openCurrents.Entity'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='ledger',
            name='is_issued',
            field=models.BooleanField(default=False),
        ),
    ]