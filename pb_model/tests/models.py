#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
from django.utils import timezone

from pb_model.models import ProtoBufMixin

from . import models_pb2


class Relation(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Relation

    num = models.IntegerField(default=0)


class M2MRelation(ProtoBufMixin, models.Model):
    pb_model = models_pb2.M2MRelation

    num = models.IntegerField(default=0)


class Main(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Main

    string_field = models.CharField(max_length=32)
    integer_field = models.IntegerField()
    float_field = models.FloatField()
    bool_field = models.BooleanField(default=False)
    datetime_field = models.DateTimeField(default=timezone.now)

    OPT0, OPT1, OPT2, OPT3 = 0, 1, 2, 3
    OPTS = [
        (OPT0, "option-0"),
        (OPT1, "option-1"),
        (OPT2, "option-2"),
        (OPT3, "option-3"),
    ]
    choices_field = models.IntegerField(default=OPT0, choices=OPTS)

    fk_field = models.ForeignKey(Relation)
    m2m_field = models.ManyToManyField(M2MRelation)
