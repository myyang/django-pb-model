#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import json
import uuid

from django.db import models
from django.conf import settings
from django.utils import timezone

from google.protobuf.descriptor import FieldDescriptor


logging.basicConfig()
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.WARNING)
if settings.DEBUG:
    LOGGER.setLevel(logging.DEBUG)


PB_FIELD_TYPE_TIMESTAMP = FieldDescriptor.MAX_TYPE + 1
PB_FIELD_TYPE_REPEATED = FieldDescriptor.MAX_TYPE + 2
PB_FIELD_TYPE_MAP = FieldDescriptor.MAX_TYPE + 3
PB_FIELD_TYPE_MESSAGE = FieldDescriptor.MAX_TYPE + 4
PB_FIELD_TYPE_REPEATED_MESSAGE = FieldDescriptor.MAX_TYPE + 5
PB_FIELD_TYPE_MESSAGE_MAP = FieldDescriptor.MAX_TYPE + 6


class ProtoBufFieldMixin(object):
    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value):
        raise NotImplementedError()

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value):
        raise NotImplementedError()


class JSONField(models.TextField):
    def from_db_value(self, value, expression, connection):
        return self._deserialize(value)

    def to_python(self, value):
        if isinstance(value, str):
            return self._deserialize(value)

        return value

    def get_prep_value(self, value):
        return json.dumps(value)

    def _deserialize(self, value):
        if value is None:
            return None

        return json.loads(value)


class ArrayField(JSONField, ProtoBufFieldMixin):
    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value):
        getattr(pb_obj, pb_field.name).extend(dj_field_value)

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value):
        setattr(instance, dj_field_name, list(pb_value))


class MapField(JSONField, ProtoBufFieldMixin):
    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value):
        getattr(pb_obj, pb_field.name).update(dj_field_value)

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value):
        setattr(instance, dj_field_name, dict(pb_value))


class RepeatedMessageField(models.ManyToManyField, ProtoBufFieldMixin):
    class Descriptor(models.fields.related_descriptors.ManyToManyDescriptor):
        def __init__(self, field_name, index_field_name, rel, reverse=False):
            super().__init__(rel, reverse)
            self._field_name = field_name
            self._index_field_name = index_field_name

        def __get__(self, instance, cls=None):
            if instance is None:
                raise AttributeError('Can only be accessed via an instance.')

            if self._field_name not in instance.__dict__:
                instance.__dict__[self._field_name] = [self.related_manager_cls(instance).get(id=id_) for id_ in getattr(instance, self._index_field_name)]
            return instance.__dict__[self._field_name]

        def __set__(self, instance, value):
            instance.__dict__[self._field_name] = value

    def __init__(self, *args, **kwargs):
        super().__init__(default=[], *args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs.pop('default')
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name):
        index_field_name = f'{name}_index'
        index_field = JSONField(default=[], editable=False, blank=True)
        index_field.creation_counter = self.creation_counter
        cls.add_to_class(index_field_name, index_field)
        super().contribute_to_class(cls, name)
        setattr(cls, self.attname, RepeatedMessageField.Descriptor(name, index_field_name, self.remote_field, reverse=False))

    def save(self, instance):
        for message in getattr(instance, self.attname):
            type(instance).__dict__[self.attname].related_manager_cls(instance).add(message)
        setattr(instance, f'{self.attname}_index', [q.id for q in instance.__dict__[self.attname]])

    def load(self, instance):
        getattr(instance, self.attname)

    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value):
        getattr(pb_obj, pb_field.name).extend([m.to_pb() for m in dj_field_value])

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value):
        related_model = instance._meta.get_field(dj_field_name).related_model
        setattr(instance, dj_field_name, [related_model().from_pb(pb_message) for pb_message in pb_value])


class MessageMapField(models.ManyToManyField, ProtoBufFieldMixin):
    class Descriptor(models.fields.related_descriptors.ManyToManyDescriptor):
        def __init__(self, field_name, index_field_name, rel, reverse=False):
            super().__init__(rel, reverse)
            self._field_name = field_name
            self._index_field_name = index_field_name

        def __get__(self, instance, cls=None):
            if instance is None:
                raise AttributeError('Can only be accessed via an instance.')

            if self._field_name not in instance.__dict__:
                instance.__dict__[self._field_name] = {key: self.related_manager_cls(instance).get(id=id_) for key, id_ in getattr(instance, self._index_field_name).items()}
            return instance.__dict__[self._field_name]

        def __set__(self, instance, value):
            instance.__dict__[self._field_name] = value

    def __init__(self, *args, **kwargs):
        super().__init__(default={}, *args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs.pop('default')
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name):
        index_field_name = f'{name}_index'
        index_field = JSONField(default={}, editable=False, blank=True)
        index_field.creation_counter = self.creation_counter
        cls.add_to_class(index_field_name, index_field)
        super().contribute_to_class(cls, name)
        setattr(cls, self.attname, MessageMapField.Descriptor(name, index_field_name, self.remote_field, reverse=False))

    def save(self, instance):
        for message in getattr(instance, self.attname).values():
            type(instance).__dict__[self.attname].related_manager_cls(instance).add(message)
        setattr(instance, f'{self.attname}_index', {key: message.id for key, message in instance.__dict__[self.attname].items()})

    def load(self, instance):
        getattr(instance, self.attname)

    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value):
        for key in dj_field_value:
            getattr(pb_obj, pb_field.name)[key].CopyFrom(dj_field_value[key].to_pb())

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value):
        related_model = instance._meta.get_field(dj_field_name).related_model
        setattr(instance, dj_field_name, {key: related_model().from_pb(pb_message) for key, pb_message in pb_value.items()})
