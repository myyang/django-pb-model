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

    def test_custom_serializer(self):
        """
        Default serialization strategies can be overriden
        """

        def serializer(pb_obj, pb_field, dj_value):
            """
            Serialize NativeRelation as a repeated int32
            """
            getattr(pb_obj, 'foreign_field').extend([dj_value.first, dj_value.second, dj_value.third])


        def deserializer(instance, dj_field_name, pb_field, pb_value):
            setattr(instance, 'foreign_field',
                    NativeRelation(
                        first=pb_value[0],
                        second=pb_value[1],
                        third=pb_value[2]
                    ))

        test_uuid = uuid.UUID('acf9d4c5-335c-4ad7-9e60-32e7306ea7c0')

        def _test_uuid_to_pb(pb_obj, pb_field, dj_field_value):
            # always set to test_uuid at test
            setattr(pb_obj, pb_field.name, test_uuid.hex)

        def _test_uuid_from_pb(instance, dj_field_name, pb_field, pb_value):
            setattr(instance, dj_field_name, uuid.UUID(pb_value))

        # This is a relation type that's not ProtoBuf enabled
        class NativeRelation(dj_models.Model):
            first = dj_models.IntegerField()
            second = dj_models.IntegerField()
            third = dj_models.IntegerField()


        class Model(ProtoBufMixin, dj_models.Model):
            pb_model = models_pb2.Root
            pb_2_dj_fields = ['foreign_field']
            pb_2_dj_field_serializers = {
                'foreign_field': (serializer, deserializer),
                dj_models.UUIDField: (_test_uuid_to_pb, _test_uuid_from_pb),
            }
            foreign_field = dj_models.ForeignKey(NativeRelation, on_delete=dj_models.DO_NOTHING)
            uuid_field = dj_models.UUIDField()

        _in = Model(
            foreign_field=NativeRelation(first=123, second=456, third=789),
            uuid_field=uuid.uuid4(),
        )

        out = Model().from_pb(_in.to_pb())

        assert out.foreign_field.first == 123
        assert out.foreign_field.second == 456
        assert out.foreign_field.third == 789

        assert _in.uuid_field != test_uuid
        assert out.uuid_field == test_uuid


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

            list_field_option=models_pb2.Root.ListWrapper(data=['qwe', 'asd', 'zxc']),

            inlineField=models_pb2.Root.InlineEmbedding(
                data="qwerty",
                doublyNestedField=models_pb2.Root.InlineEmbedding.NestedEmbedding(
                    data="qqwwee",
                ),
            ),
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

    def test_relation_depth_limit(self):
        deepter_relation_item = models.DeeperRelation.objects.create(num=2)
        relation_item = models.Relation.objects.create(
            num=1, deeper_relation=deepter_relation_item)
        main_item = models.Main.objects.create(
            string_field='Hello world', integer_field=0,
            float_field=3.14159, bool_field=True,
            choices_field=models.Main.OPT2,
            fk_field=relation_item
        )

        # Verify all relation is converted when no depth provided.
        unlimited_main_proto = main_item.to_pb()

        self.assertEqual(unlimited_main_proto.fk_field.id, relation_item.id,
                         msg="{}(src) != {}(target)".format(
                         unlimited_main_proto.fk_field.id, relation_item.id))
        self.assertEqual(unlimited_main_proto.fk_field.num, relation_item.num,
                         msg="{}(src) != {}(target)".format(
                         unlimited_main_proto.fk_field.num, relation_item.num))
        self.assertEqual(unlimited_main_proto.fk_field.deeper_relation.id,
                         deepter_relation_item.id,
                         msg="{}(src) != {}(target)".format(
                         unlimited_main_proto.fk_field.deeper_relation.id,
                         deepter_relation_item.id))
        self.assertEqual(unlimited_main_proto.fk_field.deeper_relation.num,
                         deepter_relation_item.num,
                         msg="{}(src) != {}(target)".format(
                         unlimited_main_proto.fk_field.deeper_relation.num,
                         deepter_relation_item.num))


        # Verify no relation is converted when depth = 0.
        cap_0_main_proto = main_item.to_pb(depth=0)
        # proto3 does not support `hasField`, check value not equal instead.
        self.assertNotEqual(cap_0_main_proto.fk_field.id,
                            relation_item.id,
                            msg="{}(src) == {}(target)".format(
                                cap_0_main_proto.fk_field.id,
                                relation_item.id))
        self.assertNotEqual(cap_0_main_proto.fk_field.num,
                            relation_item.num,
                            msg="{}(src) == {}(target)".format(
                                cap_0_main_proto.fk_field.num,
                                relation_item.num))
        self.assertNotEqual(
            cap_0_main_proto.fk_field.deeper_relation.id,
            deepter_relation_item.id,
            msg="{}(src) == {}(target)".format(
                cap_0_main_proto.fk_field.deeper_relation.id,
                deepter_relation_item.id))
        self.assertNotEqual(
            cap_0_main_proto.fk_field.deeper_relation.num,
            deepter_relation_item.num,
            msg="{}(src) == {}(target)".format(
                cap_0_main_proto.fk_field.deeper_relation.num,
                deepter_relation_item.num))

        # Verify only 1 level relation is converted when depth = 1.
        cap_1_main_proto = main_item.to_pb(depth=1)
        # proto3 does not support `hasField`, check value not equal instead.
        self.assertEqual(cap_1_main_proto.fk_field.id,
                         relation_item.id,
                         msg="{}(src) != {}(target)".format(
                            cap_1_main_proto.fk_field.id,
                            relation_item.id))
        self.assertEqual(cap_1_main_proto.fk_field.num,
                         relation_item.num,
                         msg="{}(src) != {}(target)".format(
                            cap_1_main_proto.fk_field.num,
                            relation_item.num))
        self.assertNotEqual(
            cap_1_main_proto.fk_field.deeper_relation.id,
            deepter_relation_item.id,
            msg="{}(src) == {}(target)".format(
                cap_1_main_proto.fk_field.deeper_relation.id,
                deepter_relation_item.id))
        self.assertNotEqual(
            cap_1_main_proto.fk_field.deeper_relation.num,
            deepter_relation_item.num,
            msg="{}(src) == {}(target)".format(
                cap_1_main_proto.fk_field.deeper_relation.num,
                deepter_relation_item.num))

    def test_reverse_relation(self):
        deeper_relation_item = models.DeeperRelation.objects.create(num=2)
        relation_item1 = models.Relation.objects.create(
            num=1, deeper_relation=deeper_relation_item)
        relation_item2 = models.Relation.objects.create(
            num=2, deeper_relation=deeper_relation_item)

        test_proto = deeper_relation_item.to_pb()
