from django.test import Client, TestCase
from django.contrib.auth.models import User

from datetime import datetime, timedelta
from django.utils import timezone

#from openCurrents import views, urls

from openCurrents.models import \
    Org, \
    Entity, \
    UserEntity, \
    OrgEntity, \
    OrgUser, \
    Project, \
    Event, \
    UserTimeLog, \
    AdminActionUserTime, \
    Ledger

from openCurrents.interfaces.ocuser import \
    OcUser, \
    InvalidUserException, \
    UserExistsException

from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo, \
    OcUser , \
    OcLedger

from openCurrents.interfaces.orgadmin import OrgAdmin

from openCurrents.interfaces.common import diffInHours

import pytz
import uuid
import random
import string

from unittest import skip


class TestUserPopup(TestCase):

    test_is_ready = False

    def setUp(self):
        # creaing org
        org = OcOrg().setup_org(name="NPF_org_1", status="npf")


        org_user = OcUser().setup_user(
            username = "volunteer1",
            email = 'volunteer1@email.cc',
            first_name='volunteer1_first_name',
            last_name= 'volunteer1_last_name'
        )

        org_user.set_password('password')
        org_user.save()

        self.client = Client()
        org_user = User.objects.filter(username="volunteer1")
        self.client.login(username='volunteer1', password='password')

    @skip("Test Is Not Ready Yet")
    def test_popup_is_on(self):
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

        print response.content

        popup='<div id="welcome-popup" class="modal center small-12 medium-9 large-7 small-centered columns popup_content" data-popup-initialized="true" aria-hidden="false" role="dialog" tabindex="-1" style="display: inline-block; outline: none; transition: all 0.75s; text-align: left; position: relative; visibility: visible; opacity: 1; vertical-align: top;">'
        self.assertInHTML(popup, response.content)



