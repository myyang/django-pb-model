#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

logging.basicConfig()
LOGGER = logging.getLogger(__name__)


class ProtoBufMixin(object):
    """This is mixin for model.Model.
    By setting attribute ``pb_model`` and ``pb_field_map``
    """

    pb_model = None
    pb_2_dj_field_map = {}    # pb field in keys, dj field in value

    def to_pb(self):
        """This is
        :returns: TODO

        """
        pass
        _pb_obj = self.pb_model()
        _dj_field_map = {f.name: f for f in self._meta.fields}
        for _f in _pb_obj.DESCRIPTOR.fields:
            LOGGER.debug("Handling field: {}".format(_f.name))
            _dj_f_name = self.pb_2_dj_field_map.get(_f.name, _f.name)
            if _dj_f_name not in _dj_field_map:
                LOGGER.debug("No such django field: {}".format(_f.name))
                continue

            try:
                _dj_f_value, _dj_f_type = getattr(self, _dj_f_name), _dj_field_map[_dj_f_name]
                if _dj_f_type.is_relation:
                    LOGGER.debug("Relation field, recursivly handling")
                    if _dj_f_type.many_to_many:
                        getattr(_pb_obj, _f.name).add(_dj_f_value.to_pb())
                    else:
                        getattr(_pb_obj, _f.name).CopyFrom(_dj_f_value.to_pb())
                else:
                    LOGGER.debug("Value field, assign field: {} = {}".format(_f.name, _dj_f_value))
                    setattr(_pb_obj, _f.name, _dj_f_value)
            except AttributeError as e:
                LOGGER.error(
                    "Fail to serialize field: {} for {}. Error: {}".format(
                        _dj_f_name, self._meta.model, e)
                )
                return None
        LOGGER.info("Protobuf object: {}".format(_pb_obj))
        return _pb_obj

    def from_pb(self, _pb_obj):
        _dj_field_map = {f.name: f for f in self._meta.fields}
        LOGGER.debug("ListFields() return fields which contains value only")
        for _f, _v in _pb_obj.ListFields():
            LOGGER.debug("Handling field: {}".format(_f.name))
            _dj_f_name = self.pb_2_dj_field_map.get(_f.name, _f.name)
            if _f.message_type is not None:
                dj_field = _dj_field_map[_dj_f_name]
                if dj_field.is_relation:
                    _v = dj_field.related.model().from_pb(_v)
            LOGGER.debug("Assign field: {} = {}".format(_f.name, _v))
            setattr(self, _dj_f_name, _v)
        LOGGER.info("Django model instance: {}".format(self))
        return self
