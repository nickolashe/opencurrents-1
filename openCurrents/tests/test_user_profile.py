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
    Ledger, \
    UserSettings

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
import re

from unittest import skip


class TestUserPopup(TestCase):

    def setUp(self):
        # creaing org
        org = OcOrg().setup_org(name="NPF_org_1", status="npf")


        #creating a volunteer that sees the popup
        oc_user = OcUser().setup_user(
            username = "volunteer_default",
            email = 'volunteer_default@email.cc',
            first_name='volunteer1_first_name',
            last_name= 'volunteer1_last_name'
        )
        oc_user.set_password('password')
        oc_user.save()


        #creating a volunteer that answered NO to the popup question
        oc_user = OcUser().setup_user(
            username = "volunteer_no",
            email = 'volunteer_no@email.cc',
            first_name='volunteer_no_first_name',
            last_name= 'volunteer_no_last_name'
        )
        oc_user.set_password('password')
        oc_user.save()

        # changing setting emulating NO answer to the tooltip
        oc_user = User.objects.get(username="volunteer_no")
        oc_user_settings = UserSettings.objects.get(user=oc_user)
        oc_user_settings.popup_reaction = False
        oc_user_settings.save()

        # setting up client
        self.client = Client()


        #creating a volunteer that answered YES to the popup question
        oc_user = OcUser().setup_user(
            username = "volunteer_yes",
            email = 'volunteer_yes@email.cc',
            first_name='volunteer_yes_first_name',
            last_name= 'volunteer_yes_last_name'
        )
        oc_user.set_password('password')
        oc_user.save()

        # changing setting emulating NO answer to the tooltip
        oc_user = User.objects.get(username="volunteer_yes")
        oc_user_settings = UserSettings.objects.get(user=oc_user)
        oc_user_settings.popup_reaction = True
        oc_user_settings.save()

        # setting up client
        self.client = Client()


    def test_user_sees_popup(self):
        #logging in user
        oc_user = User.objects.get(username="volunteer_default")
        self.client.login(username=oc_user.username, password='password')

        # did user accessed the page?
        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is in the page
        self.assertIn("$('#welcome-popup').popup({", processed_content)


    def test_user_answ_no_doesnt_see_popup(self):
        #logging in user
        oc_user = User.objects.get(username="volunteer_no")
        self.client.login(username=oc_user.username, password='password')

        # did user accessed the page?
        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is in the page
        self.assertNotIn("$('#welcome-popup').popup({", processed_content)


    def test_user_answ_yes_doesnt_see_popup(self):
        #logging in user
        oc_user = User.objects.get(username="volunteer_yes")
        self.client.login(username=oc_user.username, password='password')

        # did user accessed the page?
        response = self.client.get('/profile/')
        processed_content = re.sub(r'\s+', ' ', response.content )
        self.assertEqual(response.status_code, 200)

        # popup code is in the page
        self.assertNotIn("$('#welcome-popup').popup({", processed_content)




