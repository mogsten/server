# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2018-06-07 08:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foodtaskerapp', '0007_driver_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='extra_notes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='closing_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=6, default=None, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=6, default=None, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='opening_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
