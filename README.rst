django-pb-model
=========================

.. image:: https://travis-ci.org/myyang/django-pb-model.svg
    :target: https://travis-ci.org/myyang/django-pb-model/branches


django-pb-model provides model mixin mapping/converting protobuf message.

Compatibility
-------------

Currnetly tested with metrics:

* Python2.7, 3.4, 3.5, 3.6
* Django1.8

Install
-------

1. pip install
    
.. code:: shell

    pip install django-pb-model

2. Add django-pb to django settings.py

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
    python manage.py collectstatic -l

4. Start hacking or using app.

Usage
-----

Declare your protobuf message and compile it. For example:

.. code:: protobuf

   message Account {
       int id = 1;
       string email = 2;
       string password = 3;
   }

as `account.proto` file. Then compile it with:

.. code:: shell

   $ protoc --python_out=. account.proto

You will get `account_pb2.py`.

Now you can interact with your protobuf model, add `ProtoBufMixin` to your model like:

.. code:: python

    from django.db import models
    from pb_model.models import ProtoBufMixin
    from . import account_pb2

    class Account(ProtoBufMixin, models.Model):
        pb_model = account_pb2.Account

        email = models.EmailField(max_length=64)
        password = models.CharField(max_length=64)

        def __str__(self):
            # For demo only, encrypt password and DO NOT expose
            return "Username: {a.email}, passowrd: {a.password}".format(a=self)


By above settings, you can covert between django model and protobuf easily.

.. code:: python

   >>> account = Account.objects.create(email='user@email.com', password='passW0rd')
   >>> account.to_pb()
   email: "user@email.com"
   passord: "passW0rd"

   >>> account2 = Account()
   >>> account2.from_pb(account.to_pb())
   <Account: Username: username@mail, password: passW0rd>
   

Field details
-------------

There are several special field types while converting, read following section for more details.

Field name mapping
~~~~~~~~~~~~~~~~~~~~~

To adapt schema migration, field mapping are expected.

For example, the `email` field in previous session are alter to `username`, but we don't want to break the consistance of protobuf protocol. You may add `pb_2_dj_field_map` attribute to solve this problem. Such as:

.. code:: python

    class Account(ProtoBufMixin, models.Model):
        pb_model = account_pb2.Account
        pb_2_dj_field_map = {
            "account": "username",  # protobuf field as key and django field as value
        }

        username = models.CharField(max_length=64)
        password = models.CharField(max_length=64)


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

If this is not the format you expected, overwite `_m2m_to_protobuf()` of Django model by yourself.


Protobuf to Django
""""""""""""""""""

Same as previous section, we assume m2m field is repeated value in protobuf.
By default, **NO** operation is performed, which means
you may query current relation if your coverted django model instance has a valid PK.

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

Also, you should write your coverting policy if m2m is not nested repeated message in `_repeated_to_m2m` method

Datetime Field
~~~~~~~~~~~~~~

Datetime is a special singular value.

We currently convert between `datetime.datetime` (Python) and `google.protobuf.timestamp_pb2.Timestamp` (ProboBuf),
for example:

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

Note that if you use `USE_TZ` in Django settings, all datetime would be converted to UTC timezone while storing in protobuf message.
And coverted to default timezone in django according to settings.


LICENSE
-------

Please read LICENSE file
