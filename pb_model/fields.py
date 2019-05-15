#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
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


def _defaultfield_to_pb(pb_obj, pb_field, dj_field_value):
    """ handling any fields conversion to protobuf
    """
    LOGGER.debug("Django Value field, assign proto msg field: {} = {}".format(pb_field.name, dj_field_value))
    if sys.version_info < (3,) and type(dj_field_value) is buffer:
        dj_field_value = bytes(dj_field_value)
    setattr(pb_obj, pb_field.name, dj_field_value)


def _defaultfield_from_pb(instance, dj_field_name, pb_field, pb_value):
    """ handling any fields setting from protobuf
    """
    LOGGER.debug("Django Value Field, set dj field: {} = {}".format(dj_field_name, pb_value))
    setattr(instance, dj_field_name, pb_value)


def _datetimefield_to_pb(pb_obj, pb_field, dj_field_value):
    """handling Django DateTimeField field

    :param pb_obj: protobuf message obj which is return value of to_pb()
    :param pb_field: protobuf message field which is current processing field
    :param dj_field_value: Currently proecessing django field value
    :returns: None
    """
    if getattr(getattr(pb_obj, pb_field.name), 'FromDatetime', False):
        if settings.USE_TZ:
            dj_field_value = timezone.make_naive(dj_field_value, timezone=timezone.utc)
        getattr(pb_obj, pb_field.name).FromDatetime(dj_field_value)


def _datetimefield_from_pb(instance, dj_field_name, pb_field, pb_value):
    """handling datetime field (Timestamp) object to dj field

    :param dj_field_name: Currently target django field's name
    :param pb_value: Currently processing protobuf message value
    :returns: None
    """
    dt = pb_value.ToDatetime()
    if settings.USE_TZ:
        dt = timezone.localtime(timezone.make_aware(dt, timezone.utc))
    # FIXME: not datetime field
    setattr(instance, dj_field_name, dt)


def _uuid_to_pb(pb_obj, pb_field, dj_field_value):
    """handling Django UUIDField field

    :param pb_obj: protobuf message obj which is return value of to_pb()
    :param pb_field: protobuf message field which is current processing field
    :param dj_field_value: Currently proecessing django field value
    :returns: None
    """
    setattr(pb_obj, pb_field.name, str(dj_field_value))


def _uuid_from_pb(instance, dj_field_name, pb_field, pb_value):
    """handling string object to dj UUIDField

    :param dj_field_name: Currently target django field's name
    :param pb_value: Currently processing protobuf message value
    :returns: None
    """
    setattr(instance, dj_field_name, uuid.UUID(pb_value))


class ProtoBufFieldMixin(object):
    @staticmethod
    def to_pb(pb_obj, pb_field, dj_field_value):
        raise NotImplementedError()

    @staticmethod
    def from_pb(instance, dj_field_name, pb_field, pb_value):
        raise NotImplementedError()


class JSONField(models.TextField):
    def from_db_value(self, value, expression, connection, context=None):
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
            super(RepeatedMessageField.Descriptor, self).__init__(rel, reverse)
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
        super(RepeatedMessageField, self).__init__(default=[], *args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(RepeatedMessageField, self).deconstruct()
        kwargs.pop('default')
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name):
        index_field_name = '%s_index' % name
        index_field = JSONField(default=[], editable=False, blank=True)
        index_field.creation_counter = self.creation_counter
        cls.add_to_class(index_field_name, index_field)
        super(RepeatedMessageField, self).contribute_to_class(cls, name)
        setattr(cls, self.attname, RepeatedMessageField.Descriptor(name, index_field_name, self.remote_field, reverse=False))

    def save(self, instance):
        for message in getattr(instance, self.attname):
            type(instance).__dict__[self.attname].related_manager_cls(instance).add(message)
        setattr(instance, '%s_index' % self.attname, [q.id for q in instance.__dict__[self.attname]])

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
            super(MessageMapField.Descriptor, self).__init__(rel, reverse)
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
        super(MessageMapField, self).__init__(default={}, *args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super(MessageMapField, self).deconstruct()
        kwargs.pop('default')
        return name, path, args, kwargs

    def contribute_to_class(self, cls, name):
        index_field_name = '%s_index' % name
        index_field = JSONField(default={}, editable=False, blank=True)
        index_field.creation_counter = self.creation_counter
        cls.add_to_class(index_field_name, index_field)
        super(MessageMapField, self).contribute_to_class(cls, name)
        setattr(cls, self.attname, MessageMapField.Descriptor(name, index_field_name, self.remote_field, reverse=False))

    def save(self, instance):
        for message in getattr(instance, self.attname).values():
            type(instance).__dict__[self.attname].related_manager_cls(instance).add(message)
        setattr(instance, '%s_index' % self.attname, {key: message.id for key, message in instance.__dict__[self.attname].items()})

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
