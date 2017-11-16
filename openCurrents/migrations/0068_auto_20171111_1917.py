# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-11-11 19:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0067_transaction_price_actual'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='currents_amount',
            field=models.DecimalField(decimal_places=3, default=1, max_digits=12),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='transaction',
            name='pop_no_proof',
            field=models.CharField(max_length=8096, null=True),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='pop_image',
            field=models.ImageField(null=True, upload_to='images/redeem/%Y/%m/%d'),
        ),
    ]