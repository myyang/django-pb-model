#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import six

from django.db import models
from django.db.models.fields.reverse_related import ManyToOneRel
from django.conf import settings

from google.protobuf.descriptor import FieldDescriptor

from . import fields

logging.basicConfig()
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.WARNING)
if settings.DEBUG:
    LOGGER.setLevel(logging.DEBUG)


class DjangoPBModelError(Exception):
    pass


class Meta(type(models.Model)):
    def __init__(self, name, bases, attrs):
        super(Meta, self).__init__(name, bases, attrs)
        self.pb_2_dj_field_serializers = self._pb_2_dj_default_field_serializers.copy()
        self.pb_2_dj_field_serializers.update(attrs.get('pb_2_dj_field_serializers', {}))

        self.pb_auto_field_type_mapping = self._pb_auto_field_type_mapping.copy()
        self.pb_auto_field_type_mapping.update(attrs.get('pb_auto_field_type_mapping', {}))

        if self.pb_model is not None:
            if self.pb_2_dj_fields == '__all__':
                self.pb_2_dj_fields = self.pb_model.DESCRIPTOR.fields_by_name.keys()

            for pb_field_name in self.pb_2_dj_fields:
                pb_field_descriptor = self.pb_model.DESCRIPTOR.fields_by_name[pb_field_name]
                dj_field_name = self.pb_2_dj_field_map.get(pb_field_name, pb_field_name)
                if not isinstance(dj_field_name, dict) and dj_field_name not in attrs:
                    field = self._create_field(pb_field_descriptor)
                    if field is not None:
                        field.contribute_to_class(self, dj_field_name)

    def _create_field(self, message_field):
        message_field_type = message_field.type

        if Meta._is_message_map_field(message_field):
            mapped_message = message_field.message_type.fields_by_name['value'].message_type
            return self._create_message_map_field(message_field.containing_type.name, mapped_message.name,
                                                  message_field.name)
        elif Meta._is_map_field(message_field):
            return self._create_map_field()
        elif Meta._is_repeated_message_field(message_field):
            return self._create_repeated_message_field(message_field.containing_type.name,
                                                       message_field.message_type.name, message_field.name)
        elif Meta._is_repeated_field(message_field):
            return self._create_repeated_field()
        elif Meta._is_message_field(message_field):
            if message_field.message_type.name == 'Timestamp':
                return self._create_timestamp_field()
            elif message_field.message_type.name == 'Any':
                return self._create_protobuf_any_field()
            else:
                return self._create_message_field(message_field.containing_type.name, message_field.message_type.name,
                                                  message_field.name)
        else:
            return self._create_generic_field(message_field_type)

    @staticmethod
    def _is_message_field(field_descriptor):
        return field_descriptor.message_type is not None

    @staticmethod
    def _is_repeated_field(field_descriptor):
        return field_descriptor.label == field_descriptor.LABEL_REPEATED

    @staticmethod
    def _is_repeated_message_field(field_descriptor):
        """
        Checks if a given field is a protobuf repeated field.
        :param field_descriptor: protobuf field descriptor
        :return: bool
        """
        return Meta._is_repeated_field(field_descriptor) and Meta._is_message_field(field_descriptor)

    @staticmethod
    def _is_map_field(field_descriptor):
        """
        Checks if a given field is a protobuf map to native field (map<int/float/str/etc., int/float/str/etc.>).
        :param field_descriptor: protobuf field descriptor
        :return: bool
        """
        return field_descriptor.message_type is not None and set(
            field_descriptor.message_type.fields_by_name.keys()) == {'key', 'value'}

    @staticmethod
    def _is_message_map_field(field_descriptor):
        """
        Checks if a given field is a protobuf map to message field (map<int/float/str/etc., Message>).
        :param field_descriptor: protobuf field descriptor
        :return: bool
        """
        return Meta._is_map_field(field_descriptor) and Meta._is_message_field(
            field_descriptor.message_type.fields_by_name['value'])

    def _create_generic_field(self, type_):
        """
        Creates a django field of the type that is defined in `pb_auto_field_type_mapping`.
        :param type_: Protobuf field type.
        :return: Django field.
        """
        field_type = self.pb_auto_field_type_mapping[type_]
        return field_type(null=True)

    def _create_timestamp_field(self):
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_TIMESTAMP]
        return field_type()

    def _create_map_field(self):
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_MAP]
        return field_type()

    def _create_repeated_field(self):
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_REPEATED]
        return field_type()

    def _create_protobuf_any_field(self):
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_MESSAGE_ANY]
        return field_type()

    def _create_message_field(self, own_type, related_type, field_name):
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_MESSAGE]
        return field_type(to=related_type, related_name='%s_%s' % (own_type, field_name),
                          on_delete=models.deletion.CASCADE, null=True)

    def _create_repeated_message_field(self, own_type, related_type, field_name):
        """
        Creates a django relation that mimics a repeated message field.
        :param own_type: Name of the message that contains this field.
        :param related_type: Name of the message with which the relation is established.
        :param field_name: Name of the created field.
        :return: RepeatedMessageField
        """
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_REPEATED_MESSAGE]
        return field_type(to=related_type, related_name='%s_%s' % (own_type, field_name))

    def _create_message_map_field(self, own_type, related_type, field_name):
        """
        Creates a django relation that mimics a scalar to message map field.
        :param own_type: Name of the message that contains this field.
        :param related_type: Name of the message with which the relation is established.
        :param field_name: Name of the created field.
        :return: MapToMessageField
        """
        field_type = self.pb_auto_field_type_mapping[fields.PB_FIELD_TYPE_MESSAGE_MAP]
        return field_type(to=related_type, related_name='%s_%s' % (own_type, field_name))

class ProtoBufMixin(six.with_metaclass(Meta, models.Model)):
    """This is mixin for model.Model.
    By setting attribute ``pb_model``, you can specify target ProtoBuf Message
    to handle django model.

    By settings attribute ``pb_2_dj_field_map``, you can mapping field from
    ProtoBuf to Django to handle schema migrations and message field changes
    """

    class Meta:
        abstract = True

    pb_model = None
    pb_2_dj_fields = []  # list of pb field names that are mapped, special case pb_2_dj_fields = '__all__'
    pb_2_dj_field_map = {}  # pb field in keys, dj field in value

    # defaults for models.DateTimeField and models.UUIDField
    # these serializers would be overwrited by definition in pb_2_dj_field_serializers if any
    _pb_2_dj_default_field_serializers = {
        models.DateTimeField: (fields._datetimefield_to_pb,
                               fields._datetimefield_from_pb),
        models.UUIDField: (fields._uuid_to_pb,
                           fields._uuid_from_pb),
    }

    pb_2_dj_field_serializers = {} # dj field in key, serializer function pairs in value

    # auto gen field defaults
    # mapping would be overwrited by definition in pb_auto_field_type_mapping if any
    _pb_auto_field_type_mapping = {
        FieldDescriptor.TYPE_DOUBLE: models.FloatField,
        FieldDescriptor.TYPE_FLOAT: models.FloatField,
        FieldDescriptor.TYPE_INT64: models.BigIntegerField,
        FieldDescriptor.TYPE_UINT64: models.BigIntegerField,
        FieldDescriptor.TYPE_INT32: models.IntegerField,
        FieldDescriptor.TYPE_FIXED64: models.DecimalField,
        FieldDescriptor.TYPE_FIXED32: models.DecimalField,
        FieldDescriptor.TYPE_BOOL: models.NullBooleanField,
        FieldDescriptor.TYPE_STRING: models.TextField,
        FieldDescriptor.TYPE_BYTES: models.BinaryField,
        FieldDescriptor.TYPE_UINT32: models.PositiveIntegerField,
        FieldDescriptor.TYPE_ENUM: models.IntegerField,
        FieldDescriptor.TYPE_SFIXED32: models.DecimalField,
        FieldDescriptor.TYPE_SFIXED64: models.DecimalField,
        FieldDescriptor.TYPE_SINT32: models.IntegerField,
        FieldDescriptor.TYPE_SINT64: models.BigIntegerField,
        fields.PB_FIELD_TYPE_TIMESTAMP: models.DateTimeField,
        fields.PB_FIELD_TYPE_REPEATED: fields.ArrayField,
        fields.PB_FIELD_TYPE_MAP: fields.MapField,
        fields.PB_FIELD_TYPE_MESSAGE: models.ForeignKey,
        fields.PB_FIELD_TYPE_REPEATED_MESSAGE: fields.RepeatedMessageField,
        fields.PB_FIELD_TYPE_MESSAGE_MAP: fields.MessageMapField,
        fields.PB_FIELD_TYPE_MESSAGE_ANY: fields.ProtoBufAnyField,
    }  # pb field type in key, dj field type in value
    """
    {ProtoBuf-field-name: Django-field-name} key-value pair mapping to handle
    schema migration or any model changes.
    """

    pb_auto_field_type_mapping = {}

    default_serializers = (fields._defaultfield_to_pb, fields._defaultfield_from_pb)

    def __init__(self, *args, **kwargs):
        super(ProtoBufMixin, self).__init__(*args, **kwargs)
        for m2m_field in self._meta.many_to_many:
            if issubclass(type(m2m_field), fields.ProtoBufFieldMixin):
                m2m_field.load(self)
        # TODO: also object.update

    def save(self, *args, **kwargs):
        super(ProtoBufMixin, self).save(*args, **kwargs)
        for m2m_field in self._meta.many_to_many:
            if issubclass(type(m2m_field), fields.ProtoBufFieldMixin):
                m2m_field.save(self)
        kwargs['force_insert'] = False
        super(ProtoBufMixin, self).save(*args, **kwargs)

    def _to_pb(self, _dj_field_name, _field, _pb_obj, _dj_fields,
               _dj_pb_field_map, depth):
        _dj_f_name = _dj_pb_field_map.get(_dj_field_name, _dj_field_name)
        if _dj_f_name not in _dj_fields:
            LOGGER.warning("No such django field: {}".format(_dj_f_name))
            return
        try:
            _dj_f_value = getattr(self, _dj_f_name)
            _dj_f_type = _dj_fields[_dj_f_name]
            if _dj_f_type.null and _dj_f_value is None:
                return

            # See if there's a custom serializer for this field relation or not
            field_serializers = self._get_serializers(type(_dj_f_type), _field)
            if field_serializers and field_serializers != self.default_serializers:
                self._value_to_protobuf(_pb_obj, _field, type(_dj_f_type), _dj_f_value)
            else:
                if _dj_f_type.is_relation and not issubclass(type(_dj_f_type), fields.ProtoBufFieldMixin):
                    self._relation_to_protobuf(_pb_obj, _field, _dj_f_type, _dj_f_value, depth)
                else:
                    self._value_to_protobuf(_pb_obj, _field, type(_dj_f_type), _dj_f_value)
        except AttributeError as e:
            LOGGER.error("Fail to serialize field: {} for {}. Error: {}".format(_dj_f_name, self._meta.model, e))
            raise DjangoPBModelError(
                "Can't serialize Model({})'s field: {}. Err: {}".format(_dj_f_name, self._meta.model, e))

    def _to_proto_recursively(self, _pb_obj, _pb_dj_field_map, _dj_fields,
                              depth):
        for _pb_field in _pb_obj.DESCRIPTOR.fields:
            _dj_field_name = _pb_dj_field_map.get(_pb_field.name, _pb_field.name)
            if isinstance(_dj_field_name, dict):
                self._to_proto_recursively(getattr(_pb_obj, _pb_field.name),
                                           _dj_field_name, _dj_fields,
                                           depth=depth)
            else:
                _field = _pb_obj.DESCRIPTOR.fields_by_name[_pb_field.name]
                self._to_pb(_dj_field_name, _field, _pb_obj, _dj_fields, _pb_dj_field_map, depth=depth)

    def to_pb(self, depth=None):
        """Convert django model to protobuf instance by pre-defined name

        :param depth: depth of relation been recursively converted. None means
            unlimited, 0 means no relation will be converted.

        :returns: ProtoBuf instance
        """
        _pb_obj = self.pb_model()

        # Mapping from proto field to Django field
        _pb_to_dj_mapping = self.pb_2_dj_field_map

        # Flat list of all Django fields
        _dj_fields = {f.name: f for f in self._meta.get_fields()}

        self._to_proto_recursively(_pb_obj, _pb_to_dj_mapping, _dj_fields, depth)

        LOGGER.info("Converted Protobuf [{}]: {}".format(
            _pb_obj.DESCRIPTOR.full_name, _pb_obj))
        return _pb_obj

    def _relation_to_protobuf(self, pb_obj, pb_field, dj_field_type,
                              dj_field_value, depth):
        """Handling relation to protobuf

        :param pb_obj: protobuf message obj which is return value of to_pb()
        :param pb_field: protobuf message field which is current processing field
        :param dj_field_type: Currently processing Django field type
        :param dj_field_value: Currently processing Django field value
        :param depth: depth of relation been recursively converted. None means
            unlimited, 0 means no relation will be converted.
        :returns: None

        """
        if isinstance(dj_field_type, ManyToOneRel):
            LOGGER.debug(
                "Django Relation field '{}' is reverse related, skipping".format(
                pb_field.name))
            return
        if depth is None or depth > 0:
            LOGGER.debug(
                "Django Relation field '{}', recursively serializing".format(
                    pb_field.name))
            if (depth is not None):
                LOGGER.debug('Current depth: {}'.format(depth))
        else:
            LOGGER.debug(
                "Django Relation field '{}', capped by depth, not converting".format(
                    pb_field.name))
            return

        next_depth = depth-1 if depth is not None else None
        if dj_field_type.many_to_many:
            self._m2m_to_protobuf(pb_obj, pb_field, dj_field_value, next_depth)
        else:
            getattr(pb_obj, pb_field.name).CopyFrom(dj_field_value.to_pb(
                depth=next_depth))

    def _m2m_to_protobuf(self, pb_obj, pb_field, dj_m2m_field, next_depth):
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

        If this is not the format you expected, overwrite
        `_m2m_to_protobuf(self, pb_obj, pb_field, dj_field_value)` by yourself.

        :param pb_obj: intermediate-converting Protobuf obj, which would is return value of to_pb()
        :param pb_field: the Protobuf message field which supposed to assign after converting
        :param dj_m2mvalue: Django many_to_many field
        :param next_depth: the depth limit for the next level
        :returns: None

        """
        getattr(pb_obj, pb_field.name).extend(
            [_m2m.to_pb(depth=next_depth) for _m2m in dj_m2m_field.all()])

    def _get_serializers(self, dj_field_type, pb_field=None):
        """Getting the correct serializers for a field type

        :param dj_field_type: Currently processing django field type
        :returns: Tuple containing serialization func pair
        """
        if issubclass(dj_field_type, fields.ProtoBufFieldMixin):
            funcs = dj_field_type.to_pb, dj_field_type.from_pb
        else:
            defaults = self.default_serializers
            funcs = self.pb_2_dj_field_serializers.get(dj_field_type, None)
            if not funcs:
                if pb_field:
                    # Check by field name
                    funcs = self.pb_2_dj_field_serializers.get(pb_field.name, defaults)
                else:
                    funcs = defaults

        if len(funcs) != 2:
            LOGGER.warning(
                "Custom serializers require a pair of functions: {0} is misconfigured".
                    format(dj_field_type))
            return defaults

        return funcs

    def _value_to_protobuf(self, pb_obj, pb_field, dj_field_type, dj_field_value):
        """Handling value to protobuf

        :param pb_obj: protobuf message obj which is return value of to_pb()
        :param pb_field: protobuf message field which is current processing field
        :param dj_field_type: Currently processing django field type
        :param dj_field_value: Currently processing django field value
        :returns: None

        """
        s_funcs = self._get_serializers(dj_field_type, pb_field)
        s_funcs[0](pb_obj, pb_field, dj_field_value)

    def from_pb(self, _pb_obj):
        """Convert given protobuf obj to mixin Django model

        :returns: Django model instance
        """
        _dj_field_map = {f.name: f for f in self._meta.get_fields()}
        _pb_dj_field_map = self.pb_2_dj_field_map
        LOGGER.debug("ListFields() returns only fields which contain a value")
        self._from_pb_recursively(_dj_field_map, _pb_obj, _pb_dj_field_map)

        LOGGER.info("Converted Django model instance: {}".format(self))
        return self

    def _from_pb_recursively(self, _dj_field_map, _pb_obj, _pb_dj_field_map):
        # ListFields only returns fields with values
        for _f, _v in _pb_obj.ListFields():
            _dj_field_name = _pb_dj_field_map.get(_f.name)
            if hasattr(_v, "DESCRIPTOR") and _dj_field_name is not None:
                self._from_pb_recursively(_dj_field_map, _v, _dj_field_name)
            else:
                _dj_f_name = _dj_field_name if _dj_field_name is not None else _f.name
                self._from_pb(_dj_field_map, _f, _v, _dj_f_name)

    def _from_pb(self, _dj_field_map, _f, _v, _dj_f_name):
        _dj_f_type = _dj_field_map[_dj_f_name]

        field_serializers = self._get_serializers(type(_dj_f_type), _f)
        if field_serializers and field_serializers != self.default_serializers:
            self._protobuf_to_value(_dj_f_name, type(_dj_f_type), _f, _v)

        if _f.message_type is not None:
            dj_field = _dj_field_map[_dj_f_name]
            if dj_field.is_relation and not issubclass(type(dj_field), fields.ProtoBufFieldMixin):
                self._protobuf_to_relation(_dj_f_name, dj_field, _f, _v)
                return
        self._protobuf_to_value(_dj_f_name, type(_dj_f_type), _f, _v)

    def _protobuf_to_relation(self, dj_field_name, dj_field, pb_field,
                              pb_value):
        """Handling protobuf nested message to relation key

        :param dj_field_name: Currently target django field's name
        :param dj_field: Currently target django field
        :param pb_field: Currently processing protobuf message field
        :param pb_value: Currently processing protobuf message value
        :returns: None
        """
        LOGGER.debug("Django Relation Feild, deserializing Probobuf message")
        if dj_field.many_to_many:
            self._protobuf_to_m2m(dj_field_name, dj_field, pb_value)
            return

        if hasattr(dj_field, 'related_model'):
            # django > 1.8 compatible
            setattr(self, dj_field_name, dj_field.related_model().from_pb(pb_value))
        else:
            setattr(self, dj_field_name, dj_field.related.model().from_pb(pb_value))

    def _protobuf_to_m2m(self, dj_field_name, dj_field, pb_repeated_set):
        """
        This is hook function to handle repeated list to m2m field while converting
        from protobuf to django. By default, no operation is performed, which means
        you may query current relation if your converted django model instance has a valid PK.

        If you want to modify your database while converting on-the-fly, you may
        override the logic:

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

    def _protobuf_to_value(self, dj_field_name, dj_field_type, pb_field,
                           pb_value):
        """Handling protobuf singular value

        :param dj_field_name: Currently target django field's name
        :param dj_field_type: Currently proecessing django field type
        :param pb_field: Currently processing protobuf message field
        :param pb_value: Currently processing protobuf message value
        :returns: None
        """
        s_funcs = self._get_serializers(dj_field_type, pb_field)
        s_funcs[1](self, dj_field_name, pb_field, pb_value)
