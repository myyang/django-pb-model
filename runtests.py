#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Testcase runner:
copied from http://stackoverflow.com/a/3851333
"""

import os, sys
from django.conf import settings
from django.apps import apps

BASE_DIR = os.path.dirname(__file__)
settings.configure(
    DEBUG=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'ENCODING': 'utf-8',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    },
    INSTALLED_APPS=[
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'pb_model',
        'pb_model.tests',
    ],
    USE_TZ = True,
)

apps.populate(settings.INSTALLED_APPS)

from django.test.utils import get_runner

tr = get_runner(settings)()
failures = tr.run_tests(['pb_model', ])
if failures:
    sys.exit(bool(failures))
