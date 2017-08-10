from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render, redirect
from django.views.generic import View, ListView, TemplateView, DetailView
from django.views.generic.edit import FormView
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import F, Max
from django.views.decorators.csrf import csrf_exempt,csrf_protect
from django.template.context_processors import csrf
from datetime import datetime, time, date
from collections import OrderedDict
from copy import deepcopy
import math
import re

from openCurrents import config
from openCurrents.models import \
    Account, \
    Org, \
    OrgUser, \
    Token, \
    Project, \
    Event, \
    UserEventRegistration, \
    UserTimeLog

from openCurrents.forms import \
    UserSignupForm, \
    UserLoginForm, \
    EmailVerificationForm, \
    PasswordResetForm, \
    PasswordResetRequestForm, \
    OrgSignupForm, \
    ProjectCreateForm, \
    EventRegisterForm, \
    EventCheckinForm, \
    TrackVolunteerHours

from datetime import datetime, timedelta

import json
import mandrill
import logging
import pytz
import uuid
import decimal


logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def diffInMinutes(t1, t2):
    return round((t2 - t1).total_seconds() / 60, 1)


def diffInHours(t1, t2):
    return round((t2 - t1).total_seconds() / 3600, 1)


class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%m-%d-%Y')
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class SessionContextView(View):
    def get_context_data(self, **kwargs):
        context = super(SessionContextView, self).get_context_data(**kwargs)
        userid = self.request.user.id
        org = None
        userorgs = OrgUser.objects.filter(user__id=userid)
        if userorgs:
            org = userorgs[0].org
            context['orgid'] = org.id

        return context


class HomeView(SessionContextView, TemplateView):
    template_name = 'home.html'

class NotFoundView(SessionContextView, TemplateView):
    template_name = '404.html'

class ErrorView(SessionContextView, TemplateView):
    template_name = '500.html'


class InviteView(TemplateView):
    template_name = 'home.html'


class CheckEmailView(TemplateView):
    template_name = 'check-email.html'


class ResetPasswordView(TemplateView):
    template_name = 'reset-password.html'


class CheckEmailPasswordView(TemplateView):
    template_name = 'check-email-password.html'


class ConfirmAccountView(TemplateView):
    template_name = 'confirm-account.html'


class CommunityView(TemplateView):
    template_name = 'community.html'


class LoginView(TemplateView):
    template_name = 'login.html'


class InviteFriendsView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'invite-friends.html'

    def get_context_data(self, **kwargs):
        context = super(InviteFriendsView, self).get_context_data(**kwargs)
        try:
            account = Account.objects.get(user__username=context['referrer'])
            context['balance_pending'] = account.pending
        except:
            context['balance_pending'] = 0

        return context


class ApproveHoursView(LoginRequiredMixin, SessionContextView, ListView):
    template_name = 'approve-hours.html'
    context_object_name = 'week'

    def get_queryset(self):
        userid = self.request.user.id
        #user = User.objects.get(id=userid)
        org = OrgUser.objects.filter(user__id=userid)
        if org:
            orgid = org[0].org.id
        projects = Project.objects.filter(org__id=orgid)
        events = Event.objects.filter(
            project__in=projects
        ).filter(
            event_type='MN'
        )

        # gather unverified time logs
        timelogs = UserTimeLog.objects.filter(
            event__in=events
        ).filter(
            is_verified=False
        )

        # week list holds dictionary ordered pairs for 7 days of timelogs
        week = []

        # return nothing if unverified time logs not found
        if not timelogs:
            return week
        
        # find monday before oldest unverified time log
        oldest_timelog = timelogs.order_by('datetime_start')[0]
        week_startdate = oldest_timelog.datetime_start
        week_startdate_monday = week_startdate - timedelta(days=week_startdate.weekday())
        today = timezone.now()
        #print(week_startdate_monday)

        # build one weeks worth of timelogs starting from the oldest monday
        time_log_week = OrderedDict()
        eventtimelogs = UserTimeLog.objects.filter(
            event__in=events
        ).filter(
            datetime_start__lt=week_startdate_monday + timedelta(days=7) 
        ).filter(
            datetime_start__gte=week_startdate_monday
        ).filter(
            is_verified=False
        )


        time_log = OrderedDict()
        items = {'Total': 0}

        for timelog in eventtimelogs:
            user_email = timelog.user.email 
            name = User.objects.get(username = user_email).first_name +" "+User.objects.get(username = user_email).last_name

            # check if same day and duration longer than 15 min
            if timelog.datetime_start.date() == timelog.datetime_end.date() and timelog.datetime_end - timelog.datetime_start >= timedelta(minutes=15):
                if user_email not in time_log:
                    time_log[user_email] = OrderedDict(items)
                time_log[user_email]["name"] = name

                # time in hours rounded to nearest 15 min
                rounded_time = self.get_hours_rounded(timelog.datetime_start, timelog.datetime_end)

                # use day of week and date as key
                date_key = timelog.datetime_start.strftime('%A, %m/%d')
                if date_key not in time_log[user_email]:
                    time_log[user_email][date_key] = 0

                # add the time to the corresponding date_key and total
                time_log[user_email][date_key] += rounded_time
                time_log[user_email]['Total'] += rounded_time
            else:
                # Multiple day volunteering
                # Still working on it
                # day_diff = i.datetime_end - i.datetime_start
                # temp_date = i.datetime_start
                # while temp_date.date() != i.datetime_end.date():
                #     tt = temp_date+timedelta(days=1)
                #     tt = datetime.combine(tt, time.min).replace(tzinfo=None)
                #     tt_diff = tt - temp_date.replace(tzinfo=None)
                #     rounded_time_mdv1 = (math.ceil(self.get_hours(str(tt_diff)) * 4) / 4)
                #     time_log[str(i.user)][str(temp_date.strftime("%A"))] += rounded_time_mdv1
                #     time_log[str(i.user)]['Total'] += rounded_time_mdv1
                #     temp_date = temp_date+timedelta(days=1)
                #     rounded_time_mdv2 = (math.ceil(self.get_hours(str(temp_date.replace(tzinfo=None) - tt)) * 4) / 4)
                #     time_log[str(i.user)][str(temp_date.strftime("%A"))] += rounded_time_mdv2
                #     time_log[str(i.user)]['Total'] += rounded_time_mdv2

                # just ignore multi-day requests for now
                pass

        time_log = OrderedDict([
            (k, time_log[k])
            for k in time_log
            if time_log[k]['Total'] > 0
        ])
        logger.info('made a time_log: %s',time_log)
        if time_log:
            time_log_week[week_startdate_monday] = time_log
            week.append(time_log_week)

 
        logger.info('%s',week)
        return week

    def post(self, request):
        """
        Takes request as input which is a comma separated string which is then split to form a list with data like
        ```['a@bc.com:1:7-20-2017','abc@gmail.com:0:7-22-2017',''...]```
        """
        post_data = self.request.POST['post-data']

        templist = post_data.split(',')#eg list: ['a@bc.com:1:7-20-2017','abc@gmail.com:0:7-22-2017',''...]
        projects = []
        userid = self.request.user.id
        org = OrgUser.objects.filter(user__id=userid)
        if org:
            orgid = org[0].org.id
        for i in templist:
            """
            eg for i:
            i.split(':')[0] = 'abc@gmail.com'
            i.split(':')[1] = '0' | '1'
            i.split(':')[2] = '7-31-2017'
            """
            if i != '':
                i = str(i)

                #split the data for user, flag, and date info
                user = User.objects.get(username=i.split(':')[0])
                week_date = datetime.strptime( i.split(':')[2], '%m-%d-%Y')
                
                #build manual tracking filter, currently only accessible by OrgUser...  
                # userid = user.id
                # org = OrgUser.objects.filter(user__id=userid)#queryset of Orgs
                # for j in org:
                #     #Parse through the orglist to check ManualTracking project for the user in concern
                #     orgid = j.org.id
                #     for k in Project.objects.filter(org__id=orgid):
                #         if k.name == "ManualTracking":
                #             #Add the project in manualtracking to the projects list
                projects = Project.objects.filter(org__id=orgid)
                events = Event.objects.filter(project__in=projects).filter(event_type='MN')

                #check if the volunteer is declined and delete the same
                if i.split(':')[1] == '0':
                    time_log = UserTimeLog.objects.filter(user=user
                       ).filter(
                          datetime_start__lt=week_date + timedelta(days=7)
                       ).filter(
                          datetime_start__gte=week_date
                       ).filter(
                          is_verified=False
                       ).filter(
                          event__in=events).delete()

                #check if the volunteer is accepted and approve the same
                elif i.split(':')[1] == '1' and i !='':
                    try:
                        time_log = UserTimeLog.objects.filter(user=user
                           ).filter(
                              datetime_start__lt=week_date + timedelta(days=7)
                           ).filter(
                              datetime_start__gte=week_date
                           ).filter(
                              is_verified=False
                           ).filter(
                              event__in=events).update(is_verified=True)
                    except Exception as e:
                        logger.info('Approving timelog Error: %s',e)
                        return redirect('openCurrents:500')
                    logger.info('Approving timelog : %s',time_log)

        org = OrgUser.objects.filter(user__id=userid)
        if org:
            orgid = org[0].org.id
        projects = Project.objects.filter(org__id=orgid)
        events = Event.objects.filter(
            project__in=projects
        ).filter(
            event_type='MN'
        )

        # gather unverified time logs
        timelogs = UserTimeLog.objects.filter(
            event__in=events
        ).filter(
            is_verified=False
        )
        if not timelogs:
            return redirect('openCurrents:admin-profile')
                
        return redirect('openCurrents:approve-hours')
        #templist[:] = [item.split(':')[0] for item in templist if item != '' and item.split(':')[1]!='0']
        # try:
        #     for i in templist:
        #         user = User.objects.get(username=i)
        #         time_log = UserTimeLog.objects.filter(user=user).update(is_verified = True);
        #     return redirect('openCurrents:hours-approved')
        # except:
        #     return redirect('openCurrents:500')

    def get_hours_rounded(self, datetime_start, datetime_end):
        # h, m, s = time_str.split(':')
        # return float(h) + float(m)/60 + float(s)/3600
        return math.ceil((datetime_end - datetime_start).total_seconds() / 3600 * 4) / 4

class CausesView(TemplateView):
    template_name = 'causes.html'


class EditHoursView(TemplateView):
    template_name = 'edit-hours.html'

class ExportDataView(TemplateView):
    template_name = 'export-data.html'

class FaqView(TemplateView):
    template_name = 'faq.html'


class FindOrgsView(TemplateView):
    template_name = 'find-orgs.html'


class HoursApprovedView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'hours-approved.html'

class InventoryView(TemplateView):
    template_name = 'Inventory.html'

class MarketplaceView(TemplateView):
    template_name = 'marketplace.html'

class MissionView(TemplateView):
    template_name = 'mission.html'


class NominateView(TemplateView):
    template_name = 'nominate.html'


class NominationConfirmedView(TemplateView):
    template_name = 'nomination-confirmed.html'


class NominationEmailView(TemplateView):
    template_name = 'nomination-email.html'

class OfferView(TemplateView):
    template_name = 'offer.html'


class OrgHomeView(TemplateView):
    template_name = 'org-home.html'


class OrgSignupView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'org-signup.html'


class RequestCurrentsView(TemplateView):
    template_name = 'request-currents.html'


class SellView(TemplateView):
    template_name = 'sell.html'

class SendCurrentsView(TemplateView):
    template_name = 'send-currents.html'


class SignupView(TemplateView):
    template_name = 'signup.html'


class OrgApprovalView(TemplateView):
    template_name = 'org-approval.html'


class UserHomeView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'user-home.html'


class VerifyIdentityView(TemplateView):
    template_name = 'verify-identity.html'


class TimeTrackerView(LoginRequiredMixin, SessionContextView, FormView):
    template_name = 'time-tracker.html'
    form_class = TrackVolunteerHours
    success_url = '/time-tracked/'

    def track_hours(self, form_data):
        userid = self.request.user.id
        user = User.objects.get(id=userid)
        org = Org.objects.get(id=form_data['org'])
        tz = org.timezone

        try:
            self.project = Project.objects.get(
                    org__id=org.id,
                    name='ManualTracking'
                )
        except:
            project = Project(
                org=org,
                name='ManualTracking'
            )
            project.save()
            self.project = project

        event = Event(
            project=self.project,
            description=form_data['description'],
            event_type="MN",
            datetime_start=form_data['datetime_start'],
            datetime_end=form_data['datetime_end']
        )
        event.save()

        track = UserTimeLog(
            user=user,
            event=event,
            datetime_start=form_data['datetime_start'],
            datetime_end=form_data['datetime_end']
            )
        track.save()


    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        data = form.cleaned_data
        self.track_hours(data)
        return redirect('openCurrents:time-tracked')



class TimeTrackedView(TemplateView):
    template_name = 'time-tracked.html'


class VolunteeringView(TemplateView):
    template_name = 'volunteering.html'


class VolunteerRequestsView(TemplateView):
    template_name = 'volunteer-requests.html'

class VolunteersInvitedView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'volunteers-invited.html'

    def get_context_data(self, **kwargs):
        context = super(VolunteersInvitedView, self).get_context_data(**kwargs)
        return context



class ProfileView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'profile.html'
    login_url = "/home/"
    redirect_unauthenticated_users = True

    def get_context_data(self, **kwargs):
        context = super(ProfileView, self).get_context_data(**kwargs)
        try:
            if kwargs.pop('app_hr') == u'1':
                context['app_hr'] = 1
            else:
                context['app_hr'] = 0
        except:
            context['app_hr'] = 0
        try:
            org_name = Org.objects.get(id=context['orgid']).name
            context['orgname'] = org_name
        except:
            pass
        userid = self.request.user.id
        verified_times = UserTimeLog.objects.filter(
            user_id=userid
        ).filter(
            is_verified=True
        )

        event_user = set()

        issued_total = 0
        for timelog in verified_times:
            if not timelog.event.id in event_user:
                event_user.add(timelog.event.id)
                issued_total += (timelog.event.datetime_end - timelog.event.datetime_start).total_seconds() / 3600

                # if timelog.datetime_end and timelog.datetime_end < timelog.event.datetime_end + timedelta(hours=1):
                #     # users checked within 1 hour after the event
                #     issued_total += (timelog.datetime_end - timelog.datetime_start).total_seconds() / 3600
                # elif timelog.datetime_start <= timelog.event.datetime_end:
                #     # users that have not been checked out, use event end time
                #     issued_total += (timelog.event.datetime_end - timelog.datetime_start).total_seconds() / 3600
                # else:
                #     # if users post-added, use the event duration
                #     issued_total += (timelog.event.datetime_end - timelog.event.datetime_start).total_seconds() / 3600
            else:
                #logger.debug('user %d already counted, skipping', timelog.user.id)
                pass

        context['user_balance'] = round(issued_total, 2)

        events_upcoming = [
            userreg.event
            for userreg in UserEventRegistration.objects.filter(
                user__id=userid
            ).filter(
                event__datetime_start__gte=datetime.now(tz=pytz.utc)
            )
        ]
        context['events_upcoming'] = events_upcoming
        context['timezone'] = self.request.user.account.timezone


        return context


class AdminProfileView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'admin-profile.html'

    def get_context_data(self, **kwargs):
        context = super(AdminProfileView, self).get_context_data(**kwargs)
        orgid = context['orgid']
        org = Org.objects.get(pk=orgid)
        context['org_name'] = org.name
        context['timezone'] = org.timezone

        verified_time = UserTimeLog.objects.filter(
            event__project__org__id=orgid
        ).filter(
            is_verified=True
        )

        org_event_user = dict([
            (event.id, set())
            for event in Event.objects.filter(project__org__id=orgid)
        ])

        issued_total = 0
        for timelog in verified_time:
            if not timelog.user.id in org_event_user[timelog.event.id]:
                org_event_user[timelog.event.id].add(timelog.user.id)
                issued_total += (timelog.event.datetime_end - timelog.event.datetime_start).total_seconds() / 3600

                # if timelog.datetime_end and timelog.datetime_end < timelog.event.datetime_end + timedelta(hours=1):
                #     # users checked within 1 hour after the event
                #     issued_total += (timelog.datetime_end - timelog.datetime_start).total_seconds() / 3600
                # elif timelog.datetime_start <= timelog.event.datetime_end:
                #     # users that have not been checked out, use event end time
                #     issued_total += (timelog.event.datetime_end - timelog.datetime_start).total_seconds() / 3600
                # else:
                #     # if users post-added, use the event duration
                #     issued_total += (timelog.event.datetime_end - timelog.event.datetime_start).total_seconds() / 3600
            else:
                #logger.info('user %d already counted, skipping', timelog.user.id)
                pass

        context['issued_total'] = round(issued_total, 2)

        # past, current and upcoming events for org
        context['events_group_past'] = Event.objects.filter(
            event_type='GR',
            project__org__id=orgid,
            datetime_end__lte=datetime.now(tz=pytz.utc)
        ).order_by('-datetime_start')[:3]
        context['events_group_current'] = Event.objects.filter(
            event_type='GR',
            project__org__id=orgid,
            datetime_start__lte=datetime.now(tz=pytz.utc) + timedelta(hours=1),
            datetime_end__gte=datetime.now(tz=pytz.utc)
        )
        context['events_group_upcoming'] = Event.objects.filter(
            event_type='GR',
            project__org__id=orgid,
            datetime_start__gte=datetime.now(tz=pytz.utc) + timedelta(hours=1)
        )

        userid = self.request.user.id
        #user = User.objects.get(id=userid)
        org = OrgUser.objects.filter(user__id=userid)
        if org:
            orgid = org[0].org.id
        projects = Project.objects.filter(org__id=orgid)
        events = Event.objects.filter(
            project__in=projects
        ).filter(
            event_type='MN'
        )

        # gather unverified time logs
        timelogs = UserTimeLog.objects.filter(
            event__in=events
        ).filter(
            is_verified=False
        )

        context['user_time_log_status'] = timelogs

        return context


class EditProfileView(TemplateView):
    template_name = 'edit-profile.html'


class BlogView(TemplateView):
    template_name = 'Blog.html'


class CreateEventView(LoginRequiredMixin, SessionContextView, FormView):
    template_name = 'create-event.html'
    form_class = ProjectCreateForm
    #success_url = '/invite-volunteers/'

    def _create_event(self, location, form_data):
        if not self.project:
            project = Project(
                org=Org.objects.get(id=self.orgid),
                name=form_data['project_name']
            )
            project.save()
            self.project = project

        event = Event(
            project=self.project,
            description=form_data['description'],
            location=location,
            datetime_start=form_data['datetime_start'],
            datetime_end=form_data['datetime_end'],
            coordinator_firstname=form_data['coordinator_firstname'],
            coordinator_email=form_data['coordinator_email'],
        )
        event.save()

        return event.id

    def _get_project_names(self):
        context = super(CreateEventView, self).get_context_data()

        # obtain orgid from the session context (provided by SessionContextView)
        orgid = context['orgid']
        self.orgid = orgid

        projects = Project.objects.filter(
            org__id=self.orgid
        )
        project_names = [project.name for project in projects]

        return project_names

    def form_valid(self, form):
        project_names = self._get_project_names()

        locations = [
            val
            for (key, val) in self.request.POST.iteritems()
            if 'event-location' in key
        ]
        data = form.cleaned_data
        if data['project_name'] in project_names:
            logger.info('event found')
            self.project = Project.objects.get(
                org__id=self.orgid,
                name=data['project_name']
            )
        else:
            self.project = None

        # create an event for each location
        event_ids = map(lambda loc: self._create_event(loc, data), locations)
        print(event_ids)
        return redirect('openCurrents:invite-volunteers',event_ids[0])

    def get_context_data(self, **kwargs):
        context = super(CreateEventView, self).get_context_data()

        # context::project_names (for autocompleting the project name field)
        project_names = self._get_project_names()

        context['project_names'] = mark_safe(json.dumps(project_names))
        context['form'].fields['coordinator_firstname'].widget.attrs['value'] = str(self.request.user.first_name)
        context['form'].fields['coordinator_email'].widget.attrs['value'] = str(self.request.user.email)

        return context

    def get_form_kwargs(self):
        """
        Returns the keyword arguments for instantiating the form.
        """
        kwargs = super(CreateEventView, self).get_form_kwargs()
        kwargs.update({'orgid': self.kwargs['orgid']})
        return kwargs


class EditEventView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'edit-event.html'

    def get_context_data(self, **kwargs):
        #get the event id from admin-profile page and fetch the data need for the UI
        context = super(EditEventView, self).get_context_data(**kwargs)
        # event
        event_id = kwargs.pop('event_id')
        event = Event.objects.get(id=event_id)
        context['event'] = event
        context['start_time'] = str(event.datetime_start.time())
        context['end_time'] = str(event.datetime_end.time())
        context['date_start'] = str(event.datetime_start.date())
        return context

    def post(self, request, **kwargs):
        #POST the modified data by the user to the models
        post_data = self.request.POST
        utc=pytz.UTC
        event_id = kwargs.pop('event_id')
        edit_event = Event.objects.get(id=event_id)
        if 'save-button' in post_data:
            #if the user hits save button
            #print('save-button')
            #print(edit_event.project.org.id)
            k = []
            Organisation = OrgUser.objects.get(user__id=self.request.user.id).org.name
            if edit_event.location != str(post_data['project-location-1']) or\
               edit_event.datetime_start.replace(tzinfo=utc) != datetime.combine(datetime.strptime(post_data['project-date'], '%Y-%m-%d'),\
                  datetime.strptime(str(post_data['project-start']),'%H:%M%p').time()).replace(tzinfo=utc) or\
               edit_event.project.name != str(post_data['project-name']):
                #If some important data has been modified for the event
                volunteers = OrgUser.objects.filter(org__id=edit_event.project.org.id)
                volunteer_emails = [str(i.user.email) for i in volunteers]
                for i in volunteer_emails:
                    k.append({"email":i,"type":"to"})
                try:
                    sendBulkEmail(
                        'edit-event',
                        None,
                        [
                            {
                                'name': 'ADMIN_FIRSTNAME',
                                'content': self.request.user.first_name
                            },
                            {
                                'name': 'ADMIN_LASTNAME',
                                'content': self.request.user.last_name
                            },
                            {
                                'name': 'EVENT_TITLE',
                                'content': str(post_data['project-name'])
                            },
                            {
                                'name': 'ORG_NAME',
                                'content': Organisation
                            },
                            {
                                'name': 'EVENT_LOCATION',
                                'content': str(post_data['project-location-1'])
                            },
                            {
                                'name': 'EVENT_DATE',
                                'content': str(post_data['project-date'])
                            },
                            {
                                'name':'EVENT_START_TIME',
                                'content': str(post_data['project-start'])
                            },
                            {
                                'name':'EVENT_END_TIME',
                                'content': str(post_data['project-end'])
                            },
                            {
                                'name': 'TITLE',
                                'content': int(edit_event.project.name != str(post_data['project-name']))
                            },
                            {
                                'name': 'LOCATION',
                                'content': int(edit_event.location != str(post_data['project-location-1']))
                            },
                            {
                                'name':'TIME',
                                'content': int(edit_event.datetime_start.time().replace(tzinfo=utc) !=\
                                    datetime.strptime(str(post_data['project-start']),'%H:%M%p').time().replace(tzinfo=utc))
                            },
                            {
                                'name': 'EVENT_ID',
                                'content': event_id
                            }

                        ],
                        k,
                        self.request.user.email
                    )
                except Exception as e:
                    logger.error(
                        'unable to send email: %s (%s)',
                        e,
                        type(e)
                    )
                    return redirect('openCurrents:500')

            edit_event.description = str(post_data['project-description'])
            edit_event.location = str(post_data['project-location-1'])
            edit_event.coordinator_firstname = str(post_data['coordinator-name'])
            edit_event.coordinator_email = str(post_data['coordinator-email'])
            edit_event.datetime_start = datetime.combine(datetime.strptime(post_data['project-date'], '%Y-%m-%d'),\
                datetime.strptime(str(post_data['project-start']),'%H:%M%p').time())
            edit_event.datetime_end = datetime.combine(datetime.strptime(post_data['project-date'], '%Y-%m-%d'),\
                datetime.strptime(str(post_data['project-end']),'%H:%M%p').time())
            edit_event.save()
            project = Project.objects.get(id = edit_event.project.id)
            project.name = str(post_data['project-name'])
            project.save()
        elif 'del-button' in post_data:
            #if the user hits delete button
            edit_event.delete()
        return redirect('openCurrents:admin-profile')


# TODO: prioritize view by projects which user was invited to
class UpcomingEventsView(LoginRequiredMixin, SessionContextView, ListView):
    template_name = 'upcoming-events.html'
    context_object_name = 'events'

    def get_queryset(self):
        return Event.objects.filter(
            datetime_end__gte=datetime.now()
        )


class ProjectDetailsView(TemplateView):
    template_name = 'project-details.html'


class InviteVolunteersView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'invite-volunteers.html'

    def post(self, request, *args, **kwargs):
        userid = self.request.user.id
        #print(kwargs)
        user = User.objects.get(id=userid)
        post_data = self.request.POST
        event_create_id = None
        try:
            event_create_id = kwargs.pop('event_id')
        except:
            pass

        k = []

        OrgUsers = OrgUser.objects.filter(user__id=userid)
        if OrgUsers:
            Organisation = OrgUsers[0].org.name
        if post_data['bulk-vol'].encode('ascii','ignore') == '':
            no_of_loops = int(post_data['count-vol'])
        else:
            bulk_list = re.split(',| |\n',post_data['bulk-vol'])
            no_of_loops = len(bulk_list)
        for i in range(no_of_loops):
            if post_data['bulk-vol'].encode('ascii','ignore') == '':
                if post_data['vol-email-'+str(i+1)] != '':
                    k.append({"email":post_data['vol-email-'+str(i+1)],"type":"to"})
                    user_new = None
                    try:
                        user_new = User(
                            username=post_data['vol-email-'+str(i+1)],
                            email=post_data['vol-email-'+str(i+1)]
                            #first_name=user_firstname,
                            #last_name=user_lastname
                        )
                        user_new.save()
                    except Exception as e:
                        pass

                    if user_new and event_create_id:
                        try:
                            user_event_registration = UserEventRegistration(
                                user=user_new,
                                event=Event.objects.get(id=event_create_id),
                                is_confirmed=True
                            )
                            user_event_registration.save()
                        except Exception as e:
                            logger.error('unable to register user for event')
                else:
                    no_of_loops -= 1
            elif post_data['bulk-vol'] != '':
                k.append({"email":bulk_list[i].strip(),"type":"to"})
                user_new = None
                try:
                    user_new = User(
                        username=user_email,
                        email=user_email
                        #first_name=user_firstname,
                        #last_name=user_lastname
                    )
                    user_new.save()
                except Exception as e:
                    pass

                if user_new and event_create_id:
                    try:
                        user_event_registration = UserEventRegistration(
                            user=user_new,
                            event=Event.objects.get(event__id=event_create_id),
                            is_confirmed=True
                        )
                        user_event_registration.save()
                    except Exception as e:
                        pass
        try:
            event=Event.objects.get(id=event_create_id)
            try:
                tz = event.project.org.timezone
                sendBulkEmail(
                    'invite-volunteer-event',
                    None,
                    [
                        {
                            'name': 'ADMIN_FIRSTNAME',
                            'content': user.first_name
                        },
                        {
                            'name': 'ADMIN_LASTNAME',
                            'content': user.last_name
                        },
                        {
                            'name': 'EVENT_TITLE',
                            'content': event.project.name
                        },
                        {
                            'name': 'ORG_NAME',
                            'content': Organisation
                        },
                        {
                            'name': 'EVENT_LOCATION',
                            'content': event.location
                        },
                        {
                            'name': 'EVENT_DATE',
                            'content': str(event.datetime_start.astimezone(pytz.timezone(tz)).date().strftime('%b %d, %Y'))
                        },
                        {
                            'name':'EVENT_START_TIME',
                            'content': str(event.datetime_start.astimezone(pytz.timezone(tz)).time().strftime('%I:%M %p'))
                        },
                        {
                            'name':'EVENT_END_TIME',
                            'content': str(event.datetime_end.astimezone(pytz.timezone(tz)).time().strftime('%I:%M %p'))
                        },
                    ],
                    k,
                    user.email
                )
            except Exception as e:
                logger.error(
                    'unable to send email: %s (%s)',
                    e,
                    type(e)
                )
        except Exception as e:
            try:
                sendBulkEmail(
                    'invite-volunteer',
                    None,
                    [
                        {
                            'name': 'ADMIN_FIRSTNAME',
                            'content': user.first_name
                        },
                        {
                            'name': 'ADMIN_LASTNAME',
                            'content': user.last_name
                        },
                        {
                            'name': 'ORG_NAME',
                            'content': Organisation
                        }
                    ],
                    k,
                    user.email
                )
            except Exception as e:
                logger.error(
                    'unable to send email: %s (%s)',
                    e,
                    type(e)
                )
        return redirect('openCurrents:volunteers-invited', no_of_loops)


class EventCreatedView(TemplateView):
    template_name = 'event-created.html'


class EventDetailView(LoginRequiredMixin, SessionContextView, DetailView):
    model = Event
    context_object_name = 'event'
    template_name = 'event-detail.html'

    def get_context_data(self, **kwargs):
        context = super(EventDetailView, self).get_context_data(**kwargs)
        context['form'] = EventRegisterForm()

        return context


class LiveDashboardView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'live-dashboard.html'

    def get_context_data(self, **kwargs):
        context = super(LiveDashboardView, self).get_context_data(**kwargs)
        context['form'] = UserSignupForm()

        # event
        event_id = kwargs.pop('event_id')
        event = Event.objects.get(id=event_id)
        context['event'] = event

        # registered users
        user_regs = UserEventRegistration.objects.filter(event__id=event_id)
        registered_users = sorted(
            set([
                user_reg.user for user_reg in user_regs
            ]),
            key=lambda u: u.last_name
        )
        context['registered_users'] = registered_users

        # non-registered (existing) users
        unregistered_users = [
            ur_user
            for ur_user in User.objects.exclude(id__in=[
                r_user.id for r_user in registered_users
            ])
        ]
        context['unregistered_users'] = unregistered_users

        # dict for looking up user data by lastname
        uu_lookup = dict([
            (user.last_name, {
                'first_name': user.first_name,
                'email': user.email
            })
            for user in unregistered_users
        ])

        context['uu_lookup'] = mark_safe(json.dumps(uu_lookup))

        # identify users that are checked in
        usertimelogs = UserTimeLog.objects.filter(
            event__id=event_id
        )

        # create a map of checked in user id => checked in timestamp
        checkedin_users = {}
        for usertimelog in usertimelogs:
            if not usertimelog.datetime_end:
                if usertimelog.user.id not in checkedin_users:
                    checkedin_users[usertimelog.user.id] = usertimelog.datetime_start
                elif checkedin_users[usertimelog.user.id] < usertimelog.datetime_start:
                    checkedin_users[usertimelog.user.id] = usertimelog.datetime_start
            else:
                if usertimelog.user.id in checkedin_users:
                    checkedin_users.pop(usertimelog.user.id)

        context['checkedin_users'] = checkedin_users.keys()

        return context


class RegistrationConfirmedView(DetailView, LoginRequiredMixin):
    model = Event
    context_object_name = 'event'
    template_name = 'registration-confirmed.html'


class AddVolunteersView(TemplateView):
    template_name = 'add-volunteers.html'


@login_required
def event_checkin(request, pk):
    form = EventCheckinForm(request.POST)

    # validate form data
    if form.is_valid():
        data = form.cleaned_data
        userid = data['userid']
        checkin = data['checkin']

        event = None
        try:
            event = Event.objects.get(id=pk)
        except:
            logger.error(
                'Checkin attempted for non-existent event, userid: %s',
                request.user.id
            )

            context = {
                'errors': 'Checkin attempted for non-existent event'
            }

            return HttpResponse(status=404)

        clogger = logger.getChild(
            'user %s; event %s' % (userid, event.project.name)
        )

        if checkin:
            # create volunteer UserTimeLog
            usertimelog = UserTimeLog(
                user=User.objects.get(id=userid),
                event=event,
                datetime_start=datetime.now(tz=pytz.UTC)
            )
            usertimelog.save()
            clogger.info(
                'at %s: checkin',
                str(usertimelog.datetime_start)
            )

            # create admin/coordinator UserTimeLog only if not already done
            if not UserTimeLog.objects.filter(event__id=event.id, user__id=request.user.id):
                usertimelog = UserTimeLog(
                    user=User.objects.get(id=request.user.id),
                    event=event,
                    datetime_start=datetime.now(tz=pytz.UTC)
                )
                usertimelog.save()
    

            return HttpResponse(status=201)
        else:
            usertimelog = UserTimeLog.objects.filter(
                event__id=pk
            ).filter(
                user__id=userid
            ).latest()

            if usertimelog and not usertimelog.datetime_end:
                usertimelog.datetime_end = datetime.now(tz=pytz.utc)
                usertimelog.save()
                clogger.info(
                    'at %s: checkout',
                    str(usertimelog.datetime_end)
                )
                return HttpResponse(
                    diffInMinutes(usertimelog.datetime_start, usertimelog.datetime_end),
                    status=201
                )
            else:
                clogger.error('invalid checkout (not checked in)')
                return HttpResponse(status=400)

    else:
        logger.error('Invalid form: %s', form.errors.as_data())

        context = {
            'form': form,
            'errors': form.errors.as_data().values()[0][0]
        }

        return HttpResponse(status=400)


@login_required
def event_register(request, pk):
    form = EventRegisterForm(request.POST)

    # validate form data
    if form.is_valid():
        user = request.user
        event = Event.objects.get(id=pk)
        message = form.cleaned_data['contact_message']

        #check for existing registration
        event_records = UserEventRegistration.objects.filter(user__id=user.id, event__id=event.id, is_confirmed=True).exists()

        user_event_registration = UserEventRegistration(
            user=user,
            event=event,
            is_confirmed=True
        )
        user_event_registration.save()


        # if the volunteer entered an optional contact message, send to project coordinator
        if (message != ""):
            logger.info('User %s registered for event %s wants to send msg %s ', user.username, event.id, message)

            try:
                sendContactEmail(
                    'volunteer-messaged',
                    None,
                    [
                        {
                            'name': 'USER_FIRSTNAME',
                            'content': user.first_name
                        },
                        {
                            'name': 'USER_LASTNAME',
                            'content': user.last_name
                        },
                        {
                            'name': 'USER_EMAIL',
                            'content': user.email
                        },
                        {
                            'name': 'ADMIN_FIRSTNAME',
                            'content': event.coordinator_firstname
                        },
                        {
                            'name': 'ADMIN_EMAIL',
                            'content': event.coordinator_email
                        },
                        {
                            'name': 'MESSAGE',
                            'content': message
                        },
                        {
                            'name': 'DATE',
                            'content': json.dumps(event.datetime_start,cls=DatetimeEncoder).replace('"','')
                        }
                    ],
                    event.coordinator_email,
                    user.email
                )
            except Exception as e:
                logger.error(
                    'unable to send contact email: %s (%s)',
                    e.message,
                    type(e)
                )
        elif(not event_records):
            logger.info('User %s registered for event %s with no optional msg %s ', user.username, event.id, message)

            try:
                sendContactEmail(
                    'volunteer-registered',
                    None,
                    [
                        {
                            'name': 'USER_FIRSTNAME',
                            'content': user.first_name
                        },
                        {
                            'name': 'USER_LASTNAME',
                            'content': user.last_name
                        },
                        {
                            'name': 'USER_EMAIL',
                            'content': user.email
                        },
                        {
                            'name': 'ADMIN_FIRSTNAME',
                            'content': event.coordinator_firstname
                        },
                        {
                            'name': 'ADMIN_EMAIL',
                            'content': event.coordinator_email
                        },
                        {
                            'name': 'DATE',
                            'content': json.dumps(event.datetime_start,cls=DatetimeEncoder).replace('"','')
                        }
                    ],
                    event.coordinator_email,
                    user.email
                )
            except Exception as e:
                logger.error(
                    'unable to send contact email: %s (%s)',
                    e.message,
                    type(e)
                )

        return redirect('openCurrents:registration-confirmed', event.id)
    else:
        logger.error('Invalid form: %s', form.errors.as_data())

        context = {
            'form': form,
            'errors': form.errors.as_data().values()[0][0]
        }

        return render(
            request,
            'openCurrents/event-detail.html',
            context
        )


@login_required
def event_register_live(request, eventid):
    userid = request.POST['userid']
    user = User.objects.get(id=userid)
    event = Event.objects.get(id=eventid)
    user_event_registration = UserEventRegistration(
        user=user,
        event=event,
        is_confirmed=True
    )
    user_event_registration.save()
    logger.info('User %s registered for event %s', user.username, event.id)

    return HttpResponse({'userid': userid, 'eventid': eventid}, status=201)

# resend the verification email to a user who hits the Resend button on their check-email page
def process_resend_verification(request, user_email):

    user = User.objects.get(email=user_email)
    token_records = Token.objects.filter(email=user_email)

    # assign the last generated token in case multiple exist for one email
    token = token_records.last().token

    # resend verification email
    try:
        sendTransactionalEmail(
            'verify-email',
            None,
            [
                {
                    'name': 'FIRSTNAME',
                    'content': user.first_name
                },
                {
                    'name': 'EMAIL',
                    'content': user.email
                },
                {
                    'name': 'TOKEN',
                    'content': str(token)
                }
            ],
            user_email
        )
        status = "success"
    except Exception as e:
        logger.error(
            'unable to send transactional email: %s (%s)',
            e.message,
            type(e)
        )
        status = "fail"

    return redirect('openCurrents:check-email', user_email, status)


def process_resend_password(request, user_email):
    token_records = Token.objects.filter(email=user_email)

    # assign the last generated token in case multiple exist for one email
    token = token_records.last().token

    # resend password email
    try:
        sendTransactionalEmail(
            'password-email',
            None,
            [
                {
                    'name': 'EMAIL',
                    'content': user_email
                },
                {
                    'name': 'TOKEN',
                    'content': str(token)
                }
            ],
            user_email
        )
        status = "success"
    except Exception as e:
        logger.error(
            'unable to send transactional email: %s (%s)',
            e.message,
            type(e)
        )
        status = "fail"

    return redirect('openCurrents:check-email-password', user_email, status)




def process_signup(request, referrer=None, endpoint=False, verify_email=True):
    form = UserSignupForm(request.POST)

    # TODO: figure out a way to pass booleans in the url
    if endpoint == 'False':
        endpoint = False

    if verify_email == 'False':
        verify_email = False

    # validate form data
    if form.is_valid():
        user_firstname = form.cleaned_data['user_firstname']
        user_lastname = form.cleaned_data['user_lastname']
        user_email = form.cleaned_data['user_email']
        org_name = form.cleaned_data.get('org_name', '')

        logger.info('user %s is signing up', user_email)

        # try saving the user without password at this point
        user = None
        try:
            user = User(
                username=user_email,
                email=user_email,
                first_name=user_firstname,
                last_name=user_lastname
            )
            user.save()
        except IntegrityError:
            logger.info('user %s already exists', user_email)

            user = User.objects.get(email=user_email)
            try:
                if user.first_name=='' or user.last_name=='':
                    user.first_name = user_firstname
                    user.last_name = user_lastname
                    user.save()
                    if verify_email:
                        logger.info('Email verification requested')

                        # generate and save token
                        token = uuid.uuid4()
                        one_week_from_now = datetime.now() + timedelta(days=7)

                        token_record = Token(
                            email=user_email,
                            token=token,
                            token_type='signup',
                            date_expires=one_week_from_now
                        )

                        if referrer:
                            try:
                                token_record.referrer = User.objects.get(username=referrer)
                            except Exception as e:
                                error_msg = 'unable to locate / assign referrer: %s (%s)'
                                logger.error(error_msg, e.message, type(e))
                        else:
                            logger.info('no referrer provided')

                        token_record.save()
                        return redirect(
                            'openCurrents:confirm-account',
                            email=user_email,
                            token=token,
                            #status_msg=errors[0]
                        )
            except:
                if endpoint:
                    return HttpResponse(user.id, status=200)

                if user.has_usable_password():
                    logger.info('user %s already verified', user_email)
                    return redirect(
                        'openCurrents:login',
                        status_msg='User with this email already exists'
                    )
                else:
                    logger.info('user %s has not been verified', user_email)

        # user org
        if org_name:
            org = None
            try:
                org = Org(name=org_name)
                org.save()

                org_user = OrgUser(
                    user=user,
                    org=org
                )
                org_user.save()
            except IntegrityError:
                logger.info('org %s already exists', org_name)

        if verify_email:
            logger.info('Email verification requested')

            # generate and save token
            token = uuid.uuid4()
            one_week_from_now = datetime.now() + timedelta(days=7)

            token_record = Token(
                email=user_email,
                token=token,
                token_type='signup',
                date_expires=one_week_from_now
            )

            if referrer:
                try:
                    token_record.referrer = User.objects.get(username=referrer)
                except Exception as e:
                    error_msg = 'unable to locate / assign referrer: %s (%s)'
                    logger.error(error_msg, e.message, type(e))
            else:
                logger.info('no referrer provided')

            token_record.save()

            # send verification email
            try:
                sendTransactionalEmail(
                    'verify-email',
                    None,
                    [
                        {
                            'name': 'FIRSTNAME',
                            'content': user_firstname
                        },
                        {
                            'name': 'EMAIL',
                            'content': user_email
                        },
                        {
                            'name': 'TOKEN',
                            'content': str(token)
                        }
                    ],
                    user_email
                )
            except Exception as e:
                logger.error(
                    'unable to send transactional email: %s (%s)',
                    e.message,
                    type(e)
                )

        if endpoint:
            return HttpResponse(user.id, status=201)
        else:
            return redirect(
               'openCurrents:check-email',
               user_email
            )

    # fail with form validation error
    else:
        logger.error(
            'Invalid signup request: %s',
            form.errors.as_data()
        )

        # just report the first validation error
        errors = [
            '%s: %s' % (field, error.messages[0])
            for field, le in form.errors.as_data().iteritems()
            for error in le
        ]

        if endpoint:
            return HttpResponse({errors: errors}, status=400)
        else:
            return redirect('openCurrents:signup', status_msg=errors[0])


def process_login(request):
    form = UserLoginForm(request.POST)

    # valid form data received
    if form.is_valid():
        user_name = form.cleaned_data['user_email']
        user_password = form.cleaned_data['user_password']
        user = authenticate(
            username=user_name,
            password=user_password
        )
        if user is not None and user.is_active:
            today = date.today()
            if (user.last_login.date())< today - timedelta(days=today.weekday()):
                app_hr = '1'
            else:
                app_hr = '0'
            login(request, user)
            return redirect('openCurrents:profile', app_hr)
        else:
            return redirect('openCurrents:login', status_msg='Invalid login/password')
    else:
        logger.error(
            'Invalid login: %s',
            form.errors.as_data()
        )

        # just report the first validation error
        errors = [
            '%s: %s' % (field, error.messages[0])
            for field, le in form.errors.as_data().iteritems()
            for error in le
        ]
        return redirect('openCurrents:login', status_msg=errors[0])


def process_email_confirmation(request, user_email):
    form = EmailVerificationForm(request.POST)

    # valid form data received
    if form.is_valid():
        # first try to locate the (unverified) user object by email
        user = None
        try:
            user = User.objects.get(email=user_email)
        except Exception:
            error_msg = 'Email %s has not been registered'
            logger.error(error_msg, user_email)
            return redirect(
                'openCurrents:signup',
                status_msg=error_msg % user_email
            )

        if user.has_usable_password():
            logger.warning('user %s has already been verified', user_email)
            return redirect('openCurrents:profile')

        # second, make sure the verification token and user email match
        token_record = None
        token = form.cleaned_data['verification_token']
        try:
            token_record = Token.objects.get(
                email=user_email,
                token=token
            )
        except Exception:
            error_msg = 'Invalid verification token for %s'
            logger.error(error_msg, user_email)
            return redirect(
                'openCurrents:signup',
                status_msg=error_msg % user_email
            )

        if token_record.is_verified:
            logger.warning('token for %s has already been verified', user_email)
            return redirect('openCurrents:profile')

        # mark the verification record as verified
        token_record.is_verified = True
        token_record.save()

        # set user password (changed the user to one with password now)
        user_password = form.cleaned_data['user_password']
        user.set_password(user_password)
        user.save()

        # create user account
        user_account = Account(user=user, pending=1)

        if form.cleaned_data['monthly_updates']:
            user_account.monthly_updates = True;
        else:
            user_account.monthly_updates = False;

        user_account.save()

        # add credit to the referrer
        if token_record.referrer:
            try:
                referrer_account = Account.objects.get(
                    user=token_record.referrer
                )
                referrer_account.pending += 1
                referrer_account.save()
            except Exception as e:
                logger.error(
                    'unable to locate referrer %s account: %s (%s)',
                    token_record.referrer,
                    e.message,
                    type(e)
                )

        logger.info('verification of user %s is complete', user_email)

        # send verification email
        try:
            sendTransactionalEmail(
                'email-confirmed',
                None,
                [
                    {
                        'name': 'FIRSTNAME',
                        'content': user.first_name
                    },
                    {
                        'name': 'REFERRER',
                        'content': user.username
                    }
                ],
                user.email
            )
        except Exception as e:
            logger.error(
                'unable to send transactional email: %s (%s)',
                e.message,
                type(e)
            )

        login(request, user)

        try:
            org_user = OrgUser.objects.get(user=user)
            org_name = org_user.org.name
            return redirect('openCurrents:org-signup', org_name=org_name)

        except:
            logger.info('No org association')
            return redirect('openCurrents:profile')

    #if form was invalid for bad password, still need to preserve token
    else:
        token = form.cleaned_data['verification_token']
        logger.error(
            'Invalid email confirmation request: %s',
            form.errors.as_data()
        )

        # just report the first validation error
        errors = [
            '%s: %s' % (field, error.messages[0])
            for field, le in form.errors.as_data().iteritems()
            for error in le
        ]
        return redirect(
            'openCurrents:confirm-account',
            email=user_email,
            token=token,
            status_msg=errors[0]
        )


def password_reset_request(request):
    form = PasswordResetRequestForm(request.POST)

    # valid form data received
    if form.is_valid():
        user_email = form.cleaned_data['user_email']

    # try to locate the verified user object by email
        user = None
        try:
            user = User.objects.get(email=user_email)
        except Exception:
            error_msg = 'Email %s has not been registered'
            logger.error(error_msg, user_email)
            return redirect(
                'openCurrents:signup',
                status_msg=error_msg % user_email
            )

        if user.has_usable_password():
            logger.info('verified user %s, send password reset email', user_email)

            # generate and save token
            token = uuid.uuid4()
            one_week_from_now = datetime.now() + timedelta(days=7)

            token_record = Token(
                email=user_email,
                token=token,
                token_type='password',
                date_expires=one_week_from_now
            )

            token_record.save()

            try:
                sendTransactionalEmail(
                    'password-email',
                    None,
                    [
                        {
                            'name': 'EMAIL',
                            'content': user_email
                        },
                        {
                            'name': 'TOKEN',
                            'content': str(token)
                        }
                    ],
                    user_email
                )
            except Exception as e:
                logger.error(
                    'unable to send password email: %s (%s)',
                    e.message,
                    type(e)
                )
            return redirect('openCurrents:check-email-password', user_email)


        else:
            logger.warning('user %s has not been verified', user_email)
            return redirect('openCurrents:signup')

    # could not read email
    else:
        # just report the first validation error
        errors = [
            '%s: %s' % (field, error.messages[0])
            for field, le in form.errors.as_data().iteritems()
            for error in le
        ]
        status_msg=errors[0]
        return redirect('openCurrents:login')




def process_reset_password(request, user_email):
    form = PasswordResetForm(request.POST)

    # valid form data received
    if form.is_valid():

        new_password = form.cleaned_data['new_password']

        # first, try to locate the verified user object by email
        user = None
        try:
            user = User.objects.get(email=user_email)
        except Exception:
            error_msg = 'Email %s has not been registered'
            logger.error(error_msg, user_email)
            return redirect(
                'openCurrents:signup',
                status_msg=error_msg % user_email
            )


        # second, make sure the verification token and user email match
        token_record = None
        token = form.cleaned_data['verification_token']
        try:
            token_record = Token.objects.get(
                email=user_email,
                token=token
            )
        except Exception:
            error_msg = 'Invalid verification token for %s'
            logger.error(error_msg, user_email)
            return redirect(
                'openCurrents:signup',
                status_msg=error_msg % user_email
            )

        if token_record.is_verified:
            logger.warning('token for %s has already been verified', user_email)
            return redirect('openCurrents:profile')

        # mark the verification record as verified
        token_record.is_verified = True
        token_record.save()

        if user.has_usable_password():
            logger.info('verified user %s, allow password reset', user_email)
            user.set_password(new_password)
            user.save()
            return redirect('openCurrents:login')

        else:
            logger.warning('user %s has not been verified', user_email)
            return redirect('openCurrents:signup')

    # re-enter valid matching passwords
    else:
        token = form.cleaned_data['verification_token']

        logger.error(
            'Invalid password reset request: %s',
            form.errors.as_data()
        )

        # just report the first validation error
        errors = [
            '%s: %s' % (field, error.messages[0])
            for field, le in form.errors.as_data().iteritems()
            for error in le
        ]
        status_msg=errors[0]
        return redirect('openCurrents:reset-password', user_email, token, status_msg )



@login_required
def process_org_signup(request):
    form = OrgSignupForm(request.POST)

    # valid form data received
    if form.is_valid():
        form_data = form.cleaned_data
        org = Org(
            name=form_data['org_name'],
            website=form_data['org_website'],
            status=form_data['org_status'],
            mission=form_data['org_mission'],
            reason=form_data['org_reason']
        )
   
        # if website was not left blank, check it's not already in use
        if form_data['org_website'] != '' and Org.objects.filter(website=form_data['org_website']).exists():
            return redirect('openCurrents:org-signup', status_msg='The website provided is already in use by another organization.')

        try:
            org.save()
        except IntegrityError:
            logger.info('org at %s already exists', form_data['org_name'])
            existing = Org.objects.get(name=form_data['org_name'])
            existing.website = form_data['org_website']
            existing.status = form_data['org_status']
            if not existing.mission:
                existing.mission = form_data['org_mission']
            if not existing.reason:
                existing.reason = form_data['org_reason']
            existing.save()

        org = Org.objects.get(name=form_data['org_name'])
        org_user = OrgUser(
            org=org,
            user=request.user,
            affiliation=form_data['user_affiliation']
        )
        try:
            org_user.save()
        except IntegrityError:
            logger.info(
                'user %s is already affiliated with org %s',
                request.user.email,
                org.name
            )
            org_user = OrgUser.objects.get(
                org=org,
                user=request.user
            )
            org_user.affiliation = form_data['user_affiliation']
            org_user.save()

        logger.info(
            'Successfully created / updated org %s nominated by %s',
            org.name,
            request.user.email
        )
        return redirect(
            'openCurrents:profile',
            status_msg='Thank you for registering %s with openCurrents!' % org.name
        )

    else:
        logger.error(
            'Invalid org signup request: %s',
            form.errors.as_data()
        )

        # just report the first validation error
        errors = [
            '%s: %s' % (field, error.messages[0])
            for field, le in form.errors.as_data().iteritems()
            for error in le
        ]
        return redirect('openCurrents:org-signup', status_msg=errors[0])


@login_required
def process_logout(request):
    logout(request)
    return redirect('openCurrents:login')


def sendContactEmail(template_name, template_content, merge_vars, admin_email, user_email):
    mandrill_client = mandrill.Mandrill(config.MANDRILL_API_KEY)
    message = {
        'from_email': 'info@opencurrents.com',
        'from_name': 'openCurrents',
        'to': [{
            'email': admin_email,
            'type': 'to'
        }],
        'headers': {
            'Reply-To': user_email
        },
        'global_merge_vars': merge_vars
    }

    mandrill_client.messages.send_template(
        template_name=template_name,
        template_content=template_content,
        message=message
    )



def sendTransactionalEmail(template_name, template_content, merge_vars, recipient_email):
    mandrill_client = mandrill.Mandrill(config.MANDRILL_API_KEY)
    message = {
        'from_email': 'info@opencurrents.com',
        'from_name': 'openCurrents',
        'to': [{
            'email': recipient_email,
            'type': 'to'
        }],
        'global_merge_vars': merge_vars
    }

    mandrill_client.messages.send_template(
        template_name=template_name,
        template_content=template_content,
        message=message
    )

def sendBulkEmail(template_name, template_content, merge_vars, recipient_email, sender_email):
    mandrill_client = mandrill.Mandrill(config.MANDRILL_API_KEY)
    message = {
        'from_email': 'info@opencurrents.com',
        'from_name': 'openCurrents',
        'to': recipient_email,
        "headers": {
            "Reply-To": sender_email.encode('ascii','ignore')
        },
        'global_merge_vars': merge_vars
    }

    mandrill_client.messages.send_template(
        template_name=template_name,
        template_content=template_content,
        message=message
    )
