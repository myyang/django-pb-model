import datetime
import uuid

from django.test import TestCase
from django.db import models as dj_models

from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.descriptor import FieldDescriptor

# Create your tests here.

from pb_model.models import ProtoBufMixin
from . import models, models_pb2


class ProtoBufConvertingTest(TestCase):

    def setUp(self):
        pass

    def test_single_model(self):
        relation_item = models.Relation.objects.create(num=10)
        relation_item2 = models.Relation()

        relation_item2.from_pb(relation_item.to_pb())

        self.assertEqual(relation_item.id, relation_item2.id,
                         msg="{}(src) != {}(target)".format(relation_item.id, relation_item2.id))
        self.assertEqual(relation_item.num, relation_item2.num,
                         msg="{}(src) != {}(target)".format(relation_item.num, relation_item2.num))

    def test_model_with_key(self):
        main_item = models.Main.objects.create(
            string_field='Hello world', integer_field=2017,
            float_field=3.14159, bool_field=True,
            choices_field=models.Main.OPT2,
            fk_field=models.Relation.objects.create(num=2018),
        )
        m2m_relations = [models.M2MRelation.objects.create(num=i+2000) for i in range(5)]
        for m2m in m2m_relations:
            main_item.m2m_field.add(m2m)

        main_item2 = models.Main()
        main_item2.from_pb(main_item.to_pb())

        self.assertEqual(main_item.id, main_item2.id,
                         msg="{}(src) != {}(target)".format(main_item.id, main_item2.id))
        self.assertEqual(main_item.string_field, main_item2.string_field,
                         msg="{}(src) != {}(target)".format(main_item.string_field, main_item2.string_field))
        self.assertEqual(main_item.integer_field, main_item2.integer_field,
                         msg="{}(src) != {}(target)".format(main_item.integer_field, main_item2.integer_field))
        self.assertAlmostEqual(main_item.float_field, main_item2.float_field, delta=1e-6,
                               msg="{}(src) != {}(target)".format(main_item.float_field, main_item2.float_field))
        self.assertEqual(main_item.bool_field, main_item2.bool_field,
                         msg="{}(src) != {}(target)".format(main_item.bool_field, main_item2.bool_field))
        self.assertEqual(main_item.choices_field, main_item2.choices_field,
                         msg="{}(src) != {}(target)".format(main_item.choices_field, main_item2.choices_field))

        time_diff = main_item.datetime_field - main_item2.datetime_field
        # convertion may affect 1 microsecond due to resolution difference
        # between Protobuf timestamp and Python datetime
        self.assertAlmostEqual(0, time_diff.total_seconds(), delta=1e-6,
                               msg="{}(src) != {}(target)".format(main_item.datetime_field, main_item2.datetime_field))

        self.assertEqual(main_item.fk_field.id, main_item2.fk_field.id,
                         msg="{}(src) != {}(target)".format(main_item.fk_field.id, main_item2.fk_field.id))
        self.assertEqual(main_item.fk_field.num, main_item2.fk_field.num,
                         msg="{}(src) != {}(target)".format(main_item.fk_field.num, main_item2.fk_field.num))

        self.assertListEqual(
            list(main_item.m2m_field.order_by('id').values_list('id', flat=True)),
            list(main_item2.m2m_field.order_by('id').values_list('id', flat=True)),
            msg="{}(src) != {}(target)".format(
                main_item.m2m_field.order_by('id').values_list('id', flat=True),
                main_item2.m2m_field.order_by('id').values_list('id', flat=True))
        )
    
        main_item2.save()
        main_item2 = models.Main.objects.get()
        assert main_item.to_pb() == main_item2.to_pb()

    def test_inheritance(self):
        class Parent(ProtoBufMixin, dj_models.Model):
            pb_model = models_pb2.Root
            pb_2_dj_fields = ['uint32_field']
            pb_2_dj_field_map = {'uint32_field': 'uint32_field_renamed'}
            pb_auto_field_type_mapping = {
                FieldDescriptor.TYPE_UINT32: dj_models.IntegerField
            }

        class Child(Parent):
            pb_model = models_pb2.Root
            pb_2_dj_fields = ['uint64_field']
            pb_2_dj_field_map = {'uint64_field': 'uint64_field_renamed'}
            pb_auto_field_type_mapping = {
                FieldDescriptor.TYPE_UINT32: dj_models.FloatField,
                FieldDescriptor.TYPE_UINT64: dj_models.IntegerField
            }

        assert ProtoBufMixin.pb_auto_field_type_mapping[FieldDescriptor.TYPE_UINT32] is dj_models.PositiveIntegerField
        assert Parent.pb_auto_field_type_mapping[FieldDescriptor.TYPE_UINT32] is dj_models.IntegerField

        assert {f.name for f in Parent._meta.get_fields()} == {'child', 'id', 'uint32_field_renamed'}
        assert type(Parent._meta.get_field('uint32_field_renamed')) is dj_models.IntegerField

        assert {f.name for f in Child._meta.get_fields()} == {'parent_ptr', 'id', 'uint32_field_renamed', 'uint64_field_renamed'}
        assert type(Child._meta.get_field('uint32_field_renamed')) is dj_models.IntegerField
        assert type(Child._meta.get_field('uint64_field_renamed')) is dj_models.IntegerField

    def test_auto_fields(self):
        timestamp = Timestamp()
        timestamp.FromDatetime(datetime.datetime.now())
        pb_object = models_pb2.Root(
            uint32_field=1234,
            uint64_field=123,
            int64_field=123,
            float_field=12.3,
            double_field=12.3,
            string_field='123',
            bytes_field=b'123',
            bool_field=True,
            uuid_field=str(uuid.uuid4()),

            enum_field=1,
            timestamp_field=timestamp,
            repeated_uint32_field=[1, 2, 3],
            map_string_to_string_field={'qwe': 'asd'},

            message_field=models_pb2.Root.Embedded(data=123),
            repeated_message_field=[models_pb2.Root.Embedded(data=123), models_pb2.Root.Embedded(data=456), models_pb2.Root.Embedded(data=789)],
            map_string_to_message_field={'qwe': models_pb2.Root.Embedded(data=123), 'asd': models_pb2.Root.Embedded(data=456)},

            list_field_option=models_pb2.Root.ListWrapper(data=['qwe', 'asd', 'zxc'])
        )

        dj_object = models.Root()
        dj_object.from_pb(pb_object)
        dj_object.message_field.save()
        dj_object.message_field = dj_object.message_field
        for m in dj_object.repeated_message_field:
            m.save()
        for m in dj_object.map_string_to_message_field.values():
            m.save()
        dj_object.list_field_option.save()
        dj_object.list_field_option = dj_object.list_field_option
        dj_object.save()

        dj_object_from_db = models.Root.objects.get()
        assert [o.data for o in dj_object_from_db.repeated_message_field] == [123, 456, 789]
        assert {k: o.data for k, o in dj_object_from_db.map_string_to_message_field.items()} == {'qwe': 123, 'asd': 456}
        assert dj_object_from_db.uint32_field_renamed == pb_object.uint32_field
        result = dj_object_from_db.to_pb()
        assert pb_object == result
