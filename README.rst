django-pb-model
=========================

.. image:: https://travis-ci.org/myyang/django-pb-model.svg?branch=master
       :target: https://travis-ci.org/myyang/django-pb-model

.. image:: https://img.shields.io/pypi/v/django-pb-model.svg
       :target: https://pypi.python.org/pypi/django-pb-model
.. image:: https://coveralls.io/repos/myyang/django-pb-model/badge.svg?service=github :target: https://coveralls.io/github/myyang/django-pb-model


Django-pb-model provides model mixin mapping/converting protobuf message.
Automatic model generation from protobuf message definitions is supported.
Currently support basic value fields and naive relation conversion, including:

* Integer, String, Float, Boolean
* Choices field
* Datetime
* Foreign Key and Many-to-Many relation
* `Custom fields`_, ex: JSON

You could examine testcases_ for more details

.. _testcases: https://github.com/myyang/django-pb-model/tree/master/pb_model/tests
.. _Custom fields: https://github.com/myyang/django-pb-model#custom-fields

And PRs are always welcome :))

Table of Content
------------------------

  * Compatibility_
  * Install_
  * Usage_
  * `Automatic field generation`_
  * `Field details`_

    * `Field name mapping`_
    * `Foreign Key`_
    * `Many-to-Many field`_

      * `Django to Protobuf`_
      * `Protobuf to Django`_

    * `Limit Foreign key or Many-to-Many field conversion depth`_
    * `Datetime Field`_

      * Timezone_
    * `Any`_
    * `Custom Fields`_

      * `Built-Ins`_

Compatibility
-------------

Currently tested with matrix:

+---------------+-----+-----+-----+-----+-----+
| Django/Python | 2.7 | 3.5 | 3.6 | 3.7 | 3.8 |
+---------------+-----+-----+-----+-----+-----+
| 1.11.x        |  v  |     |     |     |     |
+---------------+-----+-----+-----+-----+-----+
| 2.2.x         |     |  v  |  v  |  v  |     |
+---------------+-----+-----+-----+-----+-----+
| 3.0.x         |     |     |  v  |  v  |  v  |
+---------------+-----+-----+-----+-----+-----+


Install
-------

1. pip install

.. code:: shell

    pip install django-pb-model

2. Add django-pb to django ``settings.py``

.. code:: python

    INSTALLED_APPS = [
        ....,
        pb_model,
        ...
    ]

3. Run python/django essential commands:

.. code:: shell

    python manage.py makemigrations
    python manage.py migrate
    python manage.py collectstatic --link

4. Start hacking or using app.

Usage
-----

Declare your protobuf message file, such as ``account.proto``, and compile it. For example:

.. code:: protobuf

   message Account {
       int id = 1;
       string email = 2;
       string nickname = 3;
   }

Then compile it with:

.. code:: shell

   $ protoc --python_out=. account.proto

You will get ``account_pb2.py``.

Now you can interact with your protobuf model, add ``ProtoBufMixin`` to your model like:

.. code:: python

    from django.db import models
    from pb_model.models import ProtoBufMixin
    from . import account_pb2

    class Account(ProtoBufMixin, models.Model):
        pb_model = account_pb2.Account

        email = models.EmailField(max_length=64)
        nickname = models.CharField(max_length=64)

        def __str__(self):
            return "Username: {a.email}, nickname: {a.nickname}".format(a=self)


By above settings, you can convert between django model and protobuf easily. For example:

.. code:: python

   >>> account = Account.objects.create(email='user@email.com', nickname='moonmoon')
   >>> account.to_pb()
   email: "user@email.com"
   nickname: "moonmoon"

   >>> account2 = Account()
   >>> account2.from_pb(account.to_pb())
   <Account: Username: username@mail, nickname: moonmoon>


Automatic field generation
--------------------------

To automatically generate django model fields based on protobuf field types.

If you don't want to manually specify fields in your django model, you can list names of desired fields under ``pb_2_dj_fields`` attribute to have those generated and added to your model automatically.

.. code:: python

    class Account(ProtoBufMixin, models.Model):
        pb_model = account_pb2.Account
        pb_2_dj_fields = ['email', 'nickname']


Alternatively if you want all protobuf fields to be mapped you can do ``pb_2_dj_fields = '__all__'``.

Fields listed in ``pb_2_dj_fields`` can be overwritten using manual definition.

.. code:: python

    class Account(ProtoBufMixin, models.Model):
        pb_model = account_pb2.Account
        pb_2_dj_fields = '__all__'

        email = models.EmailField(max_length=64)


Type of generated field depends on corresponding protobuf field type. If you want to change default field type mappings you can overwrite those using ``pb_auto_field_type_mapping`` attribute.

Following protobuf field types are supported:

* uint32, int32, uint64, int64, float, double, bool, Enum
* string, bytes
* google.protobuf.Timestamp
* google.protobuf.Any
* Messages
* oneof fields
* repeated scalar and Message fields
* map fields with scalar as key and scalar or Message as value

Field details
-------------

There are several special field types while converting, read following sections.

Field name mapping
~~~~~~~~~~~~~~~~~~~~~

To adapt schema migration, field mapping are expected.

For example, the ``email`` field in previous session is altered to ``username``, but we don't want to break the consistence of protobuf protocol. You may add ``pb_2_dj_field_map`` attribute to solve this problem. Such as:

.. code:: python

    class Account(ProtoBufMixin, models.Model):
        pb_model = account_pb2.Account
        pb_2_dj_field_map = {
            "email": "username",  # protobuf field as key and django field as value
        }

        username = models.CharField(max_length=64)
        nickname = models.CharField(max_length=64)

Foreign Key
~~~~~~~~~~~

Foreign key is a connect to another model in Django. According to this property, the foreign key could and should be converted to nested singular message in Protobuf. For example:

.. code:: Protobuf

   message Relation {
       int32 id = 1;
   }

   message Main {
       int32 id = 1;
       Relation fk = 2;
   }

Django model:

.. code:: python

   class Relation(ProtoBufMixin, models.Model):
       pb_model = models_pb2.Relation


   class Main(ProtoBufMixin, models.Model):
       pb_model = models_pb2.Main

       fk = models.ForeignKey(Relation)


With above settings, pb_model would recursively serialize and de-serialize between Django and ProtoBuf.

.. code:: python

   >>> m = Main.objects.create(fk=Relation.objects.create())
   >>> m.to_pb()
   id: 1
   fk {
       id: 1
   }

   >>> m2 = Main()
   >>> m2.from_pb(m.to_pb())
   >>> m2.fk.id
   1

Note that one can specify a reversed relation by assign related_name:

.. code:: python

  class Relation(ProtoBufMixin, models.Model):
    pb_model = models_pb2.Relation

    num = models.IntegerField(default=0)
    deeper_relation = models.ForeignKey(DeeperRelation,
                                        on_delete=models.DO_NOTHING,
                                        blank=True,
                                        null=True,
                                        related_name='relations')

When the related proto contains the same field of this reversed relation:

.. code:: Protobuf

  message DeeperRelation {
    int32 id = 1;
    int32 num = 2;
    repeated Relation relations = 3;
  }

we will skip serializes the relations field.

Many-to-Many field
~~~~~~~~~~~~~~~~~~

M2M field is a QuerySet Relation in Django.
By default, we assume target message field is "repeated" nested message, ex:

.. code:: protobuf

    message M2M {
        int32 id = 1;
    }

    message Main {
        int32 id = 1;

        repeated M2M m2m = 2;
    }

Django model would be:

.. code:: python

   class M2M(models.Model):
       pass

   class Main(models.Model):

       m2m = models.ManyToManyField(M2M)

Django to Protobuf
""""""""""""""""""

If this is not the format you expected, overwrite ``_m2m_to_protobuf()`` of Django model by yourself.

Protobuf to Django
""""""""""""""""""

Same as previous section, we assume m2m field is repeated value in protobuf.
By default, **NO** operation is performed, which means
you may query current relation if your converted django model instance has a valid primary key.

If you want to modify your database while converting on-the-fly, overwrite
logics such as:

.. code:: python

    from django.db import transaction

    ...

    class PBCompatibleModel(ProtoBufMixin, models.Model):

        def _repeated_to_m2m(self, dj_field, _pb_repeated_set):
            with transaction.atomic():
                for item in _pb_repeated_set:
                    dj_field.get_or_create(pk=item.pk, defaults={....})

        ...

Also, you should write your converting policy if m2m is not nested repeated message in ``_repeated_to_m2m`` method


Limit Foreign key or Many-to-Many field conversion depth
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, when to_pb() method is called, all related message will be
also converted recursively.

For example:

.. code:: protobuf

  message DeeperRelation {
    int32 id = 1;
    int32 num = 2;
  }

  // Relation model for testing
  message Relation {
      int32 id = 1;
      int32 num = 2;
      DeeperRelation deeper_relation = 3;
  }

  message Main {
    int32 id = 1;
    Relation fk_field = 2;
  }

And code:

.. code:: python

  >>> m = Main.objects.create(fk=Relation.objects.create(
        deeper_relation=DeeperRelation.objects.create()))
  >>> m.to_pb()
  fk {
    id: 1
    fk_field {
      id: 1,
      deeper_relation {
        id: 1
      }
    }
  }


This may not be the behavior wanted. The depth parameter can be used to limit
the depth of these conversion.

If the depth is set to 0, no related field will be converted, the fk_field in
Main message will left unset.

If the depth is set to any positive number, the level of related field will be
limited by the specified number. For example, if depth is set to 1, the fk_field
will contain the related Relation message, however the deeper_relation field
of the fk_field message will be unset.

Datetime Field
~~~~~~~~~~~~~~

Datetime is a special singular value and able to convert between
``datetime.datetime`` (Python) and ``google.protobuf.timestamp_pb2.Timestamp`` (ProboBuf)
through built-in datetime serializers. Check `Custom Fields`_ if you want other coversion rules.

Default conversion works as following example:

ProtoBuf message:

.. code:: protobuf

    package models;

    import "google/protobuf/timestamp.proto";

    message WithDatetime {
        int32 id = 1;
        google.protobuf.Timestamp datetime_field = 2;
    }

Django Model:

.. code:: python

   class WithDatetime(ProtoBufMixin, models.Model):
       pb_model = models_pb2.WithDatetime

       datetime_field = models.DatetimeField(default=timezone.now())


.. code:: python

   >>> WithDatetime.objects.create().to_pb()
   datetime_field {
   seconds: 1495119614
   nanos: 282705000
   }


Timezone
""""""""

Note that if you use ``USE_TZ`` in Django settings, all datetime would be converted to UTC timezone while storing in protobuf message.
And converted to default timezone in django according to settings.

Any
~~~~~~~~~~~~~~

When using `Any` as a field in a message, the field is by default kept as Any in your Django model and you may save it like it is any other Django Field.
Example on using `Any`:

.. code:: protobuf

    package models;

    import "google/protobuf/any.proto";

    message WithAnyMessage {
        google.protobuf.Any any_field = 1;
    }

.. code:: python

    class WithAny(ProtoBufMixin, models.Model):
        pb_model = models_pb2.WithAny

Then when you're using your Django:

.. code:: python

    >>> with_any_message = WithAnyMessage(any_field=Any())
    >>> WithAny().from_pb(with_any_message).save()

    # See that the we successfully saved Any as a Django field.
    >>> any_field = WithAny.objects.last().any_field
    >>> type(any_field)
    google.protobuf.any_pb2.Any

Custom Fields
~~~~~~~~~~~~~

You can write your own field serializers, to convert between ``django.contrib.postgres.fields.JSONField`` (Python)
and `string` (Protobuf) for example:

ProtoBuf message:

.. code:: protobuf

    package models;

    message WithJSONBlob {
        int32 id = 1;
        string json_blob = 2;
    }

Django Model:

.. code:: python

    def json_serializer(pb_obj, pb_field, dj_value):
        setattr(pb_obj, pb_field.name, json.dumps(value))

    def json_deserializer(instance, dj_field_name, pb_field, pb_value):
        setattr(instance, dj_field_name, json.loads(pb_value))

    class WithJSONField(ProtoBufMixin, models.Model):
        pb_model = models_pb2.WithJSONBlob

        pb_2_dj_field_serializers = {
            'json_blob': (json_serializer, json_deserializer),
        }

        json_blob = JSONField()

Built-Ins
"""""""""

There are 2 built-in serializers for types: ``django.models.UUIDField`` and  ``django.models.DateTimeField``.

.. code:: python

    _pb_2_dj_default_field_serializers = {
         models.DateTimeField: (fields._datetimefield_to_pb,
                                fields._datetimefield_from_pb),
         models.UUIDField: (fields._uuid_to_pb,
                            fields._uuid_from_pb),
	}

And is able to be override by declaration in ``pb_2_dj_field_serializers``.
