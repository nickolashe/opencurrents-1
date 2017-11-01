# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-10-12 05:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openCurrents', '0055_auto_20171011_0704'),
    ]

    operations = [
        migrations.RenameField(
            model_name='transaction',
            old_name='action',
            new_name='offer',
        ),
        migrations.AlterField(
            model_name='transaction',
            name='pop_image',
            field=models.ImageField(upload_to='images/redeem/%Y/%m/%d'),
        ),
    ]
