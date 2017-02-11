django-pb
=========================

django-pb provides mixin to integrate model with protobuf message.

Install
-------

1. pip install
    
    pip install django-pb

2. Add django-pb to django settings.py

    INSTALLED_APPS = [
        ....,
        pb_model,
        ...
    ]

3. Run python/django essential commands:

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


By above settings, you can covert between django model and protobuf easily.

.. code:: python

   >>> account = Account.objects.create(email='user@email.com', password='passW0rd')
   >>> account.to_pb()


   >>> account2 = Account()
   >>> account2.from_pb(account.to_pb())
   


Field mapping
~~~~~~~~~~~~~

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


LICENSE
-------

Please read LICENSE file
