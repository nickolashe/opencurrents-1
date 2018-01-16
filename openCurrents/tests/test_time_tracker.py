from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django.core import mail
from django.shortcuts import redirect

from openCurrents.models import \
    Org, \
    Event, \
    Ledger, \
    AdminActionUserTime, \
    UserEntity, \
    UserTimeLog, \
    Project, \
    OrgUser

from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.orgs import \
    OcOrg, \
    OrgUserInfo

from datetime import date, datetime, timedelta
from django.utils import timezone
import pytz
import urllib
from unittest import skip



class TestTimeTracker(TestCase):

    def setUp(self):

        # creating org
        self.org = OcOrg().setup_org(name="NPF_org_1", status="npf")

        # volunteer user
        self.volunteer1 = OcUser().setup_user(
            username='test_user_1',
            email='test_user_1@e.com',
        )

        # npf admin 1
        self.npf_admin_1 = OcUser().setup_user(
            username='npf_admin_1',
            email='npf_admin_1@g.com',
        )
        oui = OrgUserInfo(self.npf_admin_1.id)
        oui.setup_orguser(self.org)
        oui.make_org_admin(self.org.id)

        # npf admin 2
        self.npf_admin_2 = OcUser().setup_user(
            username='npf_admin_2',
            email='npf_admin_2@g.com',
        )
        oui = OrgUserInfo(self.npf_admin_2.id)
        oui.setup_orguser(self.org)

        for user in User.objects.all():
            user.set_password('password')
            user.save()

        # Datestart
        date_start = timezone.now() - timedelta(days=1)
        self.date_start = date_start.strftime('%Y-%m-%d')

        # setting up client
        self.client = Client()



    def test_vol_hours_existing_org_and_adm(self):

        self.client.login(username=self.volunteer1.username, password='password')
        self.response = self.client.get('/time-tracker/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/time-tracker/", {
            'description':'test manual tracker existing NPF org and admin',
            'date_start':self.date_start,
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
        user_time_log = Event.objects.all()[0].usertimelog_set.filter(user=self.volunteer1)

        # assert a proper user time log has been created
        self.assertEqual(len(Event.objects.all()[0].usertimelog_set.filter(id=1)), 1)
        self.assertIn('test_user_1 contributed 1.0 hr', unicode(user_time_log[0]))

        # assert UserTimeLog is created for volunteer1 and isn't verified
        self.assertEqual(len(user_time_log.filter(is_verified = False)), 1)

        # assert there is a requested action
        self.assertEqual(len(AdminActionUserTime.objects.filter(action_type='req')), 1)
        # assert requested action came from volunteer
        self.assertEqual(len(AdminActionUserTime.objects.filter(usertimelog__user=self.volunteer1).filter(action_type='req')), 1)
        # assert there are no approved actions
        self.assertEqual(len(AdminActionUserTime.objects.filter(action_type='app')), 0)


    def test_vol_hours_existing_org_new_adm(self):

        self.client.login(username=self.volunteer1.username, password='password')
        session = self.client.session

        self.response = self.client.get('/time-tracker/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/time-tracker/", {
            'description':'test manual tracker existing NPF org, non-existing NPF admin',
            'date_start':self.date_start,
            'admin':'other-admin',
            'org':self.org.id,
            'new_admin_name':'new_npf_admin',
            'new_admin_email':'new_npf_admin@e.co',
            'time_start':'7:00am',
            'time_end':'8:00am',
            'test_time_tracker_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # asserting that transactional email function has been launched with proper templates
        self.assertEqual(self.client.session['transactional'], '1')
        self.assertEqual(self.client.session['admin_template'], 'volunteer-invites-admin')
        self.assertEqual(self.client.session['biz_template'], 'new-admin-invited')

        # assert if we've been redirected
        self.assertRedirects(response, '/time-tracked/', status_code=302)

        # assert a MT project was created
        self.assertEqual(len(Project.objects.all()), 1)
        self.assertEqual(Project.objects.all()[0].org, self.org)
        self.assertIn('ManualTracking', Project.objects.all()[0].__unicode__())
        self.assertIn('NPF_org_1', Project.objects.all()[0].__unicode__())

        # assert a MT event was created
        self.assertEqual(len(Event.objects.all()), 1)
        self.assertEqual(Event.objects.all()[0].project, Project.objects.all()[0])
        self.assertEqual(Event.objects.all()[0].description, 'test manual tracker existing NPF org, non-existing NPF admin')
        self.assertEqual(Event.objects.all()[0].event_type, 'MN')

        # assert createdion of a proper MT user_time_log instance
        user_time_log = UserTimeLog.objects.all().filter(user=self.volunteer1)[0]
        self.assertEqual(len(UserTimeLog.objects.all()), 1)
        self.assertIn('test_user_1 contributed 1.0 hr. to NPF_org_1', unicode(user_time_log))
        self.assertEqual(user_time_log.is_verified, False)


        # assert Admin action user time has been created 'req'
        self.assertEqual(len(AdminActionUserTime.objects.filter(action_type='req')), 1)
        self.assertEqual(len(AdminActionUserTime.objects.filter(usertimelog__user=self.volunteer1).filter(action_type='req')), 1)
        self.assertEqual(len(AdminActionUserTime.objects.filter(action_type='app')), 0)

        # assert creation of a new NPF user with new name, email, no password
        self.assertEqual(len(User.objects.all()),4)
        self.assertEqual(len(User.objects.filter(username='new_npf_admin@e.co')),1)



    def test_vol_hours_new_org_new_adm(self):

        self.client.login(username=self.volunteer1.username, password='password')
        session = self.client.session

        self.response = self.client.get('/time-tracker/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/time-tracker/", {
            'description':'test manual tracker non-existing NPF org and admin',
            'new_org':'new_npf_org',
            'new_admin_name':'new_npf_admin',
            'new_admin_email':'new_npf_admin@e.co',
            'date_start':self.date_start,
            'time_start':'7:00am',
            'time_end':'8:00am',
            'test_time_tracker_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # asserting that transactional email function has been launched with proper templates
        self.assertEqual(self.client.session['transactional'], '1')
        self.assertEqual(self.client.session['admin_template'], 'volunteer-invites-org')
        self.assertEqual(self.client.session['biz_template'], 'new-org-invited')

        # assert if we've been redirected
        self.assertRedirects(response, '/time-tracked/', status_code=302)

        # assert a MT event wasn't created
        self.assertEqual(len(Event.objects.all()), 0)

        # assert new org wasn't created (one org is created during setup)
        self.assertEqual(len(Org.objects.all()), 1)

        # assert new project wasn't created
        self.assertEqual(len(Project.objects.all()), 0)

        # assert new usertimelog wasn't created
        self.assertEqual(len(UserTimeLog.objects.all()), 0)



    def test_vol_hours_existing_org_existing_adm_as_someone_else(self):

        self.client.login(username=self.volunteer1.username, password='password')
        self.response = self.client.get('/time-tracker/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/time-tracker/", {
            'description':'test manual tracker existing NPF org and admin',
            'date_start':self.date_start,
            'admin':'other-admin',
            'org':self.org.id,
            'new_admin_name':self.npf_admin_1.username,
            'new_admin_email':self.npf_admin_1.email,
            'time_start':'7:00am',
            'time_end':'8:00am',
            'test_time_tracker_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.npf_admin_1.email, response.url)
        self.assertIn(self.org.name, response.url)
        self.assertIn('/time-tracker/', response.url)


        # assert a MT event wasn't created
        self.assertEqual(len(Event.objects.all()), 0)

        # # assert there is a requested action
        self.assertEqual(len(AdminActionUserTime.objects.filter(action_type='req')), 0)

        # assert there are no approved actions
        self.assertEqual(len(AdminActionUserTime.objects.filter(action_type='app')), 0)


    def test_vol_hours_existing_org_existing_non_approved_adm_as_someone_else(self):

        self.client.login(username=self.volunteer1.username, password='password')
        session = self.client.session

        self.response = self.client.get('/time-tracker/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/time-tracker/", {
            'description':'test manual tracker existing NPF org and admin',
            'date_start':self.date_start,
            'admin':'other-admin',
            'org':self.org.id,
            'new_admin_name':self.npf_admin_2.username,
            'new_admin_email':self.npf_admin_2.email,
            'time_start':'7:00am',
            'time_end':'8:00am',
            'test_time_tracker_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertRedirects(response, '/time-tracked/', status_code=302)

        # asserting that transactional email function has been launched
        self.assertEqual(session['transactional'], '1')
        # asserting that transactional email function has been launched with proper templates
        self.assertEqual(self.client.session['transactional'], '1')
        self.assertEqual(self.client.session['admin_template'], 'volunteer-invites-admin')
        self.assertEqual(self.client.session['biz_template'], 'new-admin-invited')

        # assert a MT event was created
        self.assertEqual(len(Event.objects.all()), 1)

        # assert new org wasn't created (one org is created during setup)
        self.assertEqual(len(Org.objects.all()), 1)

        # assert new project was created
        self.assertEqual(len(Project.objects.all()), 1)

        # assert new usertimelog was created
        self.assertEqual(len(UserTimeLog.objects.all()), 1)

        # asserting adminaction
        self.assertEqual(len(AdminActionUserTime.objects.filter(usertimelog__user=self.volunteer1)), 1)



    def test_vol_hours_new_org_existing_adm(self):

        self.client.login(username=self.volunteer1.username, password='password')
        self.response = self.client.get('/time-tracker/')

        self.assertEqual(self.response.status_code, 200)

        # posting form
        response = self.client.post("/time-tracker/", {
            'description':'test manual tracker non-existing NPF org and admin',
            'new_org':'new_npf_org',
            'new_admin_name':self.npf_admin_1.username,
            'new_admin_email':self.npf_admin_1.email,
            'date_start':self.date_start,
            'time_start':'7:00am',
            'time_end':'8:00am',
            'test_time_tracker_mode':'1' # letting know the app that we're testing, so it shouldnt send emails via Mandrill
            })

        # assert if we've been redirected
        self.assertEqual(response.status_code, 302)

        self.assertIn(u'The coordinator is already affiliated with an existing organization', urllib.url2pathname(response.url))
        self.assertIn('/time-tracker/', urllib.url2pathname(response.url))


        # assert a MT event wasn't created
        self.assertEqual(len(Event.objects.all()), 0)

        # # assert there is a requested action
        self.assertEqual(len(AdminActionUserTime.objects.filter(action_type='req')), 0)

        # assert there are no approved actions
        self.assertEqual(len(AdminActionUserTime.objects.filter(action_type='app')), 0)
