from django.test import TestCase

# Create your tests here.

from . import models


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
