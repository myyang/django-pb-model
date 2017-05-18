#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import datetime

from django.conf import settings
from django.utils import timezone

from google.protobuf.timestamp_pb2 import Timestamp

logging.basicConfig()
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.WARNING)
if settings.DEBUG:
    LOGGER.setLevel(logging.DEBUG)


class DjangoPBModelError(Exception):
    pass


class ProtoBufMixin(object):
    """This is mixin for model.Model.
    By setting attribute ``pb_model``, you can specify target ProtoBuf Message
    to handle django model.

    By settings attribute ``pb_2_dj_field_map``, you can mapping field from
    ProtoBuf to Django to handle schema migrations and message field chnages
    """

    pb_model = None
    pb_2_dj_field_map = {}    # pb field in keys, dj field in value
    """
    {ProtoBuf-field-name: Django-field-name} key-value pair mapping to handle
    schema migration or any model changes.
    """

    def to_pb(self):
        """Convert django model to protobuf instance by pre-defined name

        :returns: ProtoBuf instance
        """
        _pb_obj = self.pb_model()
        _dj_field_map = {f.name: f for f in self._meta.get_fields()}
        for _f in _pb_obj.DESCRIPTOR.fields:
            _dj_f_name = self.pb_2_dj_field_map.get(_f.name, _f.name)
            if _dj_f_name not in _dj_field_map:
                LOGGER.warning("No such django field: {}".format(_f.name))
                continue
            try:
                _dj_f_value, _dj_f_type = getattr(self, _dj_f_name), _dj_field_map[_dj_f_name]
                if _dj_f_type.is_relation:
                    self._relation_to_protobuf(_pb_obj, _f, _dj_f_type, _dj_f_value)
                else:
                    self._value_to_protobuf(_pb_obj, _f, _dj_f_type, _dj_f_value)
            except AttributeError as e:
                LOGGER.error(
                    "Fail to serialize field: {} for {}. Error: {}".format(
                        _dj_f_name, self._meta.model, e)
                )
                raise DjangoPBModelError(
                    "Can't serialize Model({})'s field: {}. Err: {}".format(
                        _dj_f_name, self._meta.model, e))

        LOGGER.info("Coverted Protobuf object: {}".format(_pb_obj))
        return _pb_obj

    def _relation_to_protobuf(self, pb_obj, pb_field, dj_field_type, dj_field_value):
        """Handling relation to protobuf

        :param pb_obj: protobuf message obj which is return value of to_pb()
        :param pb_field: protobuf message field which is current processing field
        :param dj_field_type: Currently proecessing django field type
        :param dj_field_value: Currently proecessing django field value
        :returns: None

        """
        LOGGER.debug("Django Relation field, recursivly serializing")
        if dj_field_type.many_to_many:
            self._m2m_to_protobuf(pb_obj, pb_field, dj_field_value)
        else:
            getattr(pb_obj, pb_field.name).CopyFrom(dj_field_value.to_pb())

    def _m2m_to_protobuf(self, pb_obj, pb_field, dj_m2m_field):
        """
        This is hook function from m2m field to protobuf. By default, we assume
        target message field is "repeated" nested message, ex:

        ```
        message M2M {
            int32 id = 1;
        }

        message Main {
            int32 id = 1;

            repeated M2M m2m = 2;
        }
        ```

        If this is not the format you expected, overwite
        `_m2m_to_protobuf(self, pb_obj, pb_field, dj_field_value)` by yourself.

        :param pb_obj: intermedia-converting Protobuf obj, which would is return value of to_pb()
        :param pb_field: the Protobuf message field which supposed to assign after converting
        :param dj_m2mvalue: Django many_to_many field
        :returns: None

        """
        getattr(pb_obj, pb_field.name).extend(
            [_m2m.to_pb() for _m2m in dj_m2m_field.all()])

    def _value_to_protobuf(self, pb_obj, pb_field, dj_field_type, dj_field_value):
        """Handling value to protobuf

        :param pb_obj: protobuf message obj which is return value of to_pb()
        :param pb_field: protobuf message field which is current processing field
        :param dj_field_type: Currently proecessing django field type
        :param dj_field_value: Currently proecessing django field value
        :returns: None

        """
        if isinstance(dj_field_value, datetime.datetime):
            self._handling_dj_dt_field(pb_obj, pb_field, dj_field_value)
            return
        LOGGER.debug("Django Value field, assign proto msg field: {} = {}".format(pb_field.name, dj_field_value))
        setattr(pb_obj, pb_field.name, dj_field_value)

    def _handling_dj_dt_field(self, pb_obj, pb_field, dj_field_value):
        """ handling Djangodatetime field

        :param pb_obj: protobuf message obj which is return value of to_pb()
        :param pb_field: protobuf message field which is current processing field
        :param dj_field_value: Currently proecessing django field value
        :returns: None
        """
        if getattr(getattr(pb_obj, pb_field.name), 'FromDatetime', False):
            if settings.USE_TZ:
                dj_field_value = timezone.make_naive(dj_field_value, timezone=timezone.UTC)
            getattr(pb_obj, pb_field.name).FromDatetime(dj_field_value)
            return
        # FIXME: not timestamp field

    def from_pb(self, _pb_obj):
        """Convert given protobuf obj to mixin Django model

        :returns: Django model instance
        """
        _dj_field_map = {f.name: f for f in self._meta.get_fields()}
        LOGGER.debug("ListFields() return fields which contains value only")
        for _f, _v in _pb_obj.ListFields():
            _dj_f_name = self.pb_2_dj_field_map.get(_f.name, _f.name)
            if _f.message_type is not None:
                dj_field = _dj_field_map[_dj_f_name]
                if dj_field.is_relation:
                    self._protobuf_to_relation(_dj_f_name, dj_field, _f, _v)
                    continue
            self._protobuf_to_value(_dj_f_name, _f, _v)
        LOGGER.info("Coveretd Django model instance: {}".format(self))
        return self

    def _protobuf_to_relation(self, dj_field_name, dj_field, pb_field, pb_value):
        """Handling protobuf nested message to relation key

        :param dj_field_name: Currently target django field's name
        :param dj_field: Currently target django field
        :param pb_field: Currently processing protobuf message field
        :param pb_value: Currently processing protobuf message value
        :returns: None
        """
        LOGGER.debug("Django Relation Feild, deserializing Probobuf message")
        if dj_field.many_to_many:
            self._protobuf_to_m2m(dj_field, pb_value)
            return
        setattr(self, dj_field_name, dj_field.related.model().from_pb(pb_value))

    def _protobuf_to_m2m(self, dj_field, pb_repeated_set):
        """
        This is hook function to handle repeated list to m2m field while converting
        from protobuf to django. By default, no operation is performed, which means
        you may query current relation if your coverted django model instance has a valid PK.

        If you want to modify your database while converting on-the-fly, overwrite
        logics such as:

        ```
        from django.db import transaction

        ...

        class PBCompatibleModel(ProtoBufMixin, models.Model):

            def _repeated_to_m2m(self, dj_field, _pb_repeated_set):
                with transaction.atomic():
                    for item in _pb_repeated_set:
                        dj_field.get_or_create(pk=item.pk, defaults={....})

            ...

        ```

        :param dj_field: Django many_to_many field
        :param pb_repeated_set: the Protobuf message field which contains data that is going to be converted
        :returns: None

        """
        return

    def _protobuf_to_value(self, dj_field_name, pb_field, pb_value):
        """Handling protobuf singular value

        :param dj_field_name: Currently target django field's name
        :param pb_field: Currently processing protobuf message field
        :param pb_value: Currently processing protobuf message value
        :returns: None
        """
        LOGGER.debug("Django Value Field, set dj field: {} = {}".format(dj_field_name, pb_value))
        if isinstance(pb_value, Timestamp):
            self._handling_pb_dt_field(dj_field_name, pb_value)
            return
        setattr(self, dj_field_name, pb_value)

    def _handling_pb_dt_field(self, dj_field_name, pb_value):
        """handling datetime field (Timestamp) object to dj field

        :param dj_field_name: Currently target django field's name
        :param pb_value: Currently processing protobuf message value
        :returns: None
        """
        dt = pb_value.ToDatetime()
        if settings.USE_TZ:
            dt = timezone.make_aware(dt, timezone.utc)
        # FIXME: not datetime field
        setattr(self, dj_field_name, dt)
