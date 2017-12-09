from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.core import mail
from django.shortcuts import redirect

from openCurrents.models import \
    Org, \
    Event

from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo

from datetime import date, datetime, timedelta
import pytz


class TestTimeTracker(TestCase):

    def setUp(self):

        # creating org
        self.org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # volunteer user
        self.volunteer1 = OcUser().setup_user(
            username='test_user_1',
            email='test_user_1@e.com',
        )

        # npf admin
        self.npf_admin_1 = OcUser().setup_user(
            username='npf_admin_1',
            email='npf_admin_1@g.com',
        )
        oui = OrgUserInfo(self.npf_admin_1.id)
        oui.setup_orguser(self.org)
        oui.make_org_admin(self.org.id)

        for user in User.objects.all():
            user.set_password('password')
            user.save()

        # setting up client
        self.client = Client()



    def test_vol_hours_existing_org_and_adm(self):

        self.client.login(username=self.volunteer1.username, password='password')
        self.response = self.client.get('/time-tracker/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/time-tracker/", {
            'description':'test manual tracker description',
            'date_start':'2017-12-07',
            'admin':self.npf_admin_1.id,
            'org':self.org.id,
            'new_admin_name':'',
            'time_start':'7:00am',
            'time_end':'8:00am',
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/time-tracked/', status_code=302)

        # assert a MT event was created
        self.assertEqual(len(Event.objects.all()), 1)

        # created user_time_log instance
        user_time_log = Event.objects.all()[0].usertimelog_set.filter(id=1)[0]

        # assert a proper user time log has been created
        self.assertEqual(len(Event.objects.all()[0].usertimelog_set.filter(id=1)), 1)
        self.assertIn('test_user_1 contributed 1.0 hr', unicode(user_time_log))

        # assert creator's id == volunteer1.id
        self.assertEqual(user_time_log.user.id, self.volunteer1.id)


    def test_vol_hours_existing_org_new_adm(self):

        self.client.login(username=self.volunteer1.username, password='password')
        self.response = self.client.get('/time-tracker/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/time-tracker/", {
            'description':'test manual tracker description',
            'date_start':'2017-12-07',
            'admin':'other-admin',
            'org':self.org.id,
            'new_admin_name':'new_npf_admin',
            'new_admin_email':'new_npf_admin@e.co',
            'time_start':'7:00am',
            'time_end':'8:00am',
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/time-tracked/', status_code=302)

        # assert a MT event was created
        self.assertEqual(len(Event.objects.all()), 0)


    def test_vol_hours_new_org_new_adm(self):

        self.client.login(username=self.volunteer1.username, password='password')
        self.response = self.client.get('/time-tracker/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/time-tracker/", {
            'description':'test manual tracker description',
            'date_start':'2017-12-07',
            'admin':'other-admin',
            'org':self.org.id,
            'new_admin_name':'new_npf_admin',
            'new_admin_email':'new_npf_admin@e.co',
            'new_org': 'new_npf_org',
            'time_start':'7:00am',
            'time_end':'8:00am',
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/time-tracked/', status_code=302)

        # assert a MT event was created
        self.assertEqual(len(Event.objects.all()), 0)