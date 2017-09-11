from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.views.generic import View, ListView, TemplateView, DetailView
from django.views.generic.edit import FormView
from django.contrib.auth.models import User, Group
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import F, Q, Max
from django.views.decorators.csrf import csrf_exempt,csrf_protect
from django.template.context_processors import csrf
from datetime import datetime, time, date
from collections import OrderedDict
from copy import deepcopy
from orgs import OrgUserInfo


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
    UserTimeLog, \
    AdminActionUserTime

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
    OrgNominationForm, \
    TimeTrackerForm

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

# Create and save a new group for admins of a new org
def new_org_admins_group(orgid):
    org_admins_name = 'admin_' + str(orgid)
    logger.info('Creating new org_admins group: %s', org_admins_name)
    org_admins = Group(name=org_admins_name)
    try:
        org_admins.save()
    except IntegrityError:
        logger.info('org %s already exists', orgid)

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
        context['userid'] = userid
        orguser = OrgUserInfo(userid)
        orgid = orguser.get_org_id()
        context['orgid'] = orgid
        context['org_id'] = orgid

        is_admin = False
        admin_org_group_names = [
            '_'.join(['admin', str(userorg.org.id)])
            for userorg in orguser.get_orguser()
        ]
        admin_org_groups = Group.objects.filter(
            name__in=admin_org_group_names,
            user__id=userid
        )
        if admin_org_groups:
            is_admin = True

        context['is_admin'] = is_admin
        return context


class OrgAdminPermissionMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        user = request.user

        # check if the user is logged in
        if not user.is_authenticated():
            return self.handle_no_permission()

        # try to obtain user => org mapping
        org_id = None
        try:
            org_id = kwargs['org_id']
        except KeyError:
            userorgs = OrgUserInfo(self.request.user.id)
            org_id = userorgs.get_org_id()

        if org_id is None:
            logger.error('user %d with no org', user.id)
            return redirect('openCurrents:500')

        try:
            event_id = kwargs['event_id']
            event = Event.objects.get(id=event_id)
            org_id = event.project.org.id
        except KeyError, Event.DoesNotExist:
            pass

        #logger.debug('authorize request for org id %d', org_id)
        org_admin_group_name = '_'.join(['admin', str(org_id)])

        # group is supposed to exist at this point
        try:
            org_admin_group = Group.objects.get(name=org_admin_group_name)
        except Group.DoesNotExist:
            logger.error("org exists without an admin group")
            return redirect('openCurrents:500')

        # check if user is in org admin group
        if not org_admin_group.user_set.filter(id=user.id):
            logger.warning("insufficient permission for user %s", user.username)
            return redirect('openCurrents:403')

        # user has sufficient permissions
        return super(OrgAdminPermissionMixin, self).dispatch(
            request, *args, **kwargs
        )


class HomeView(SessionContextView, TemplateView):
    template_name = 'home.html'

    def dispatch(self, *args, **kwargs):
        try:
            #If there is session set for profile
            if self.request.session['profile']:
                return redirect('openCurrents:profile')
        except:
            #If no session set
            return super(HomeView, self).dispatch(*args, **kwargs)


class ForbiddenView(SessionContextView, TemplateView):
    template_name = '403.html'


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


class AssignAdminsView(TemplateView):
    template_name = 'assign-admins.html'


class BusinessView(TemplateView):
    template_name = 'business.html'


class CheckEmailPasswordView(TemplateView):
    template_name = 'check-email-password.html'


class CommunitiesView(TemplateView):
    template_name = 'communities.html'


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


class ApproveHoursView(OrgAdminPermissionMixin, SessionContextView, ListView):
    template_name = 'approve-hours.html'
    context_object_name = 'week'

    def get_queryset(self,**kwargs):
        userid = self.request.user.id
        orguserinfo = OrgUserInfo(userid)
        orgid = orguserinfo.get_org_id()
        projects = Project.objects.filter(org__id=orgid)
        events = Event.objects.filter(
            project__in=projects
        ).filter(
            event_type='MN'
        )

        # fetch unverified time logs
        requested_actions = AdminActionUserTime.objects.filter(
            user__id=userid
        ).filter(
            action_type='req'
        ).filter(
            usertimelog__is_verified = False
        ).filter(
            usertimelog__event__in=events
        )

        # week list holds dictionary ordered pairs for 7 days of timelogs
        week = []

        # return kwargs vols_approved and vols_declined if unverified time logs not found
        if not requested_actions:
            week = self.kwargs
            return week

        # find monday before oldest unverified time log
        earliest_request = requested_actions.order_by('usertimelog__datetime_start').first()
        week_startdate = earliest_request.usertimelog.datetime_start
        week_startdate_monday = (week_startdate - timedelta(days=week_startdate.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # get the weeks timelog; week starting from "week_startdate_monday"
        # TODO (@karbmk): can you describe the difference between main_timelog and local_timelog
        # and why we need both?
        main_timelog = self.weeks_timelog(week_startdate_monday, today)
        actions = main_timelog[0]
        time_log_week = main_timelog[1]

        # check usertimelogs for up to a month ahead 
        week_num = 0
        today = timezone.now()

        while week_num < 5:
            if not actions:
                # get the weeks timelog till it's not empty for a month;
                # week starting from "week_startdate_monday"
                local_timelog = self.weeks_timelog(
                    week_startdate_monday + timedelta(days=7 * (week_num + 1)),
                    today
                )
                actions = local_timelog[0]
                time_log_week = local_timelog[1]
                k += 1
            else:
                break


        time_log = OrderedDict()
        items = {'Total': 0}

        for action in actions:
            user_timelog = action.usertimelog
            volunteer_user = user_timelog.user
            name = ' '.join([volunteer_user.first_name, volunteer_user.last_name])

            # check if same day and duration longer than 15 min
            if user_timelog.datetime_start.date() == user_timelog.datetime_end.date() and user_timelog.datetime_end - user_timelog.datetime_start >= timedelta(minutes=15):
                user_email = volunteer_user.email
                if user_email not in time_log:
                    time_log[user_email] = OrderedDict(items)
                time_log[user_email]["name"] = name

                # time in hours rounded to nearest 15 min
                rounded_time = self.get_hours_rounded(user_timelog.datetime_start, user_timelog.datetime_end)

                # use day of week and date as key
                date_key = user_timelog.datetime_start.strftime('%A, %m/%d')
                if date_key not in time_log[user_email]:
                    time_log[user_email][date_key] = [0]

                # add the time to the corresponding date_key and total
                tz = orguserinfo.get_org_timezone()
                st_time = user_timelog.datetime_start.astimezone(pytz.timezone(tz)).time().strftime('%-I:%M %p')
                end_time = user_timelog.datetime_end.astimezone(pytz.timezone(tz)).time().strftime('%-I:%M %p')
                time_log[user_email][date_key][0] += rounded_time
                time_log[user_email][date_key].append(st_time+" - "+end_time+": "+str(user_timelog.event.description))
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

        # include post kwargs vols_approved vols_declined as last part of week
        week.append(self.kwargs)

        logger.debug('%s',week)
        return week

    def weeks_timelog(self, week_startdate_monday, today):
        # build one week worth of timelogs starting from the oldest monday
        userid = self.request.user.id
        orguserinfo = OrgUserInfo(userid)
        orgid = orguserinfo.get_org_id()
        projects = Project.objects.filter(org__id=orgid)
        events = Event.objects.filter(
            project__in=projects
        ).filter(
            event_type='MN'
        )
        time_log_week = OrderedDict()
        requested_actions = self.get_requested_actions(week_startdate_monday, events)
 
        return [requested_actions, time_log_week]

    def get_requested_actions(self, week_date, events, user=None):
        # fetches the volunteer-requested hours for admin review
        logger.info(week_date)
        requested_actions = AdminActionUserTime.objects.filter(
            user_id=self.request.user.id
        ).filter(
            usertimelog__datetime_start__gte=week_date
        ).filter(
            usertimelog__datetime_end__lt=week_date + timedelta(days=7)
        ).filter(
            action_type='req'
        ).filter(
            usertimelog__is_verified=False
        ).filter(
            usertimelog__event__in=events
        )
        logger.info(requested_actions)
        if user:
            logger.info(user.id)

            requested_actions = requested_actions.filter(usertimelog__user__id=user.id)

        return requested_actions


    def post(self, request, **kwargs):
        """
        Takes request as input which is a comma separated string which is then split to form a list with data like
        ```['a@bc.com:1:7-20-2017','abc@gmail.com:0:7-22-2017',''...]```
        """
        vols_approved = 0
        vols_declined = 0

        # TODO (@karbmk): see the comment below re: parsing raw request data
        post_data = self.request.POST['post-data']

        action_type_map = {
            0: 'dec',
            1: 'app',
            2: 'def'
        }

        templist = post_data.split(',')#eg list: ['a@bc.com:1:7-20-2017','abc@gmail.com:0:7-22-2017',''...]
        logger.info(
            'templist: %s', templist
        )

        admin_userid = self.request.user.id
        org = OrgUserInfo(admin_userid)
        orgid = org.get_org_id()

        projects = Project.objects.filter(org__id=orgid)
        events = Event.objects.filter(
            project__in=projects
        ).filter(
            event_type='MN'
        )

        for i in templist:
            """
            eg for i:
            i.split(':')[0] = 'abc@gmail.com'
            i.split(':')[1] = '0' | '1'
            i.split(':')[2] = '7-31-2017'
            """
            if not i:
                continue

            i = str(i)
            # split the data for user, action_type, and date info
            # action_type denotes approval or declining by admin
            # TODO (@karbmk): since we are parsing raw request data,
            # are we validating the input anywhere yet?
            # Let's switch to doing this using forms ASAP
            user = User.objects.get(username=i.split(':')[0])
            action_code = int(i.split(':')[1])
            action_type = action_type_map[action_code]
            week_date = datetime.strptime(i.split(':')[2], '%m-%d-%Y')

            # fetch volunteer requests for admin review
            requested_actions = self.get_requested_actions(week_date, events, user)
            logger.info('requested_actions: %s', requested_actions)

            if action_type == 'app':
                # for approved hours, additionally set is_verified boolean on usertimelogs
                for action in requested_actions:
                    usertimelog = action.usertimelog
                    usertimelog.is_verified = True
                    usertimelog.save()
                    logger.debug(
                        'volunteer %s hours have been %s by admin %s',
                        usertimelog.user_id,
                        action_type,
                        admin_userid
                    )
                vols_approved += 1
   
            if action_type == 'dec':
                vols_declined += 1

            # volunteer deferred
            # TODO: decide if we need to keep this
            elif action_type == 'def':
                logger.warning('deferred timelog (legacy warning): %s', declined)

            # TODO (@karbmk): instead of updating the requests for approval,
            # we should create a new action respresenting the action taken and save it
            for action in requested_actions:
                action.action_type=action_type
                action.save()

        # lastly, determine if there any approval requests remaining
        usertimelogs = UserTimeLog.objects.filter(
            event__in=events
        ).filter(
            is_verified=False
        ).annotate(
            last_action_created=Max('adminactionusertime__date_created')
        )

        # admin-specific requests
        admin_requested_hours = AdminActionUserTime.objects.filter(
            user_id=admin_userid
        ).filter(
            date_created__in=[
                utl.last_action_created for utl in usertimelogs
            ]
        ).filter(
            action_type='req'
        )        

        redirect_url = 'approve-hours' if admin_requested_hours else 'admin-profile'

        return redirect(
            'openCurrents:%s' % redirect_url,
            vols_approved,
            vols_declined
        )


    def get_hours_rounded(self, datetime_start, datetime_end):
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


class NonprofitView(TemplateView):
    template_name = 'nonprofit.html'


class OfferView(TemplateView):
    template_name = 'offer.html'


class OrgHomeView(TemplateView):
    template_name = 'org-home.html'


class OrgSignupView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'org-signup.html'


class OurStoryView(TemplateView):
    template_name = 'our-story.html'


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
    form_class = TimeTrackerForm

    def track_hours(self, form_data):
        userid = self.request.user.id
        user = User.objects.get(id=userid)
        org = Org.objects.get(id=form_data['org'])
        tz = org.timezone

        #If the time is same or within the range of already existing tracking
        track_exists_1 = UserTimeLog.objects.filter(
                user = user
            ).filter(
                datetime_start__gte = form_data['datetime_start']
            ).filter(
                datetime_end__lte = form_data['datetime_end']
            )
        #If the time is same or Part of it where start time is earlier and end time is greater than end time
        track_exists_2 = UserTimeLog.objects.filter(
                user = user
            ).filter(
                datetime_start__lte = form_data['datetime_start']
            ).filter(
                datetime_end__gte = form_data['datetime_end']
            )
        #If the time is same or Part of it where start time is earlier and end time falls in the range
        track_exists_3 = UserTimeLog.objects.filter(
                user = user
            ).filter(
                datetime_start__lt = form_data['datetime_start']
            ).filter(
                datetime_end__lt = form_data['datetime_end']
            ).filter(
                datetime_end__gt = form_data['datetime_start']
            )
        #If the time is same or Part of it where start time is greater but within the end-time and end time doesn't matter
        track_exists_4 = UserTimeLog.objects.filter(
                user = user
            ).filter(
                datetime_start__gt = form_data['datetime_start']
            ).filter(
                datetime_end__gt = form_data['datetime_end']
            ).filter(
                datetime_start__lt = form_data['datetime_end']
            )

        track_existing_choices = [
            track_exists_1,
            track_exists_2,
            track_exists_3,
            track_exists_4
        ]

        for track in track_existing_choices:
            if track:
                # tracked time overlaps with existing time log
                track_existing_datetime_start = track[0].datetime_start
                track_existing_datetime_end = track[0].datetime_end
                status_time = ' '.join([
                    'You have already submitted hours from',
                    track_existing_datetime_start.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p'),
                    'to',
                    track_existing_datetime_end.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p'),
                    'on',
                    track_existing_datetime_start.strftime('%-m/%-d')
                ])
                logger.info(status_time)

                #return redirect('openCurrents:time-tracker', status_time)
                return False, status_time

        if form_data['admin'].isdigit():
            # create admin-specific approval request
            project = None
            try:
                project = Project.objects.get(
                        org__id=org.id,
                        name='ManualTracking'
                    )
            except Project.DoesNotExist:
                project = Project(
                    org=org,
                    name='ManualTracking'
                )
                project.save()

            event = Event(
                project=project,
                description=form_data['description'],
                event_type="MN",
                datetime_start=form_data['datetime_start'],
                datetime_end=form_data['datetime_end']
            )
            event.save()

            usertimelog = UserTimeLog(
                user=user,
                event=event,
                datetime_start=form_data['datetime_start'],
                datetime_end=form_data['datetime_end']
                )
            usertimelog.save()
            self.create_approval_request(org.id, usertimelog, form_data['admin'])

            return True, None

        elif form_data['admin'] == 'other-admin':
            # TODO (@karbmk): switch to using forms
            admin_name = self.request.POST['admin_fname']
            admin_email = self.request.POST['admin_email']
            if admin_email:
                user = self.invite_new_admin(org, admin_email, admin_name)

                # as of now, do not submit hours prior to admin registering
                #self.create_approval_request(org.id,usertimelog,user)
                return True, None
            else:
                return False, 'Please enter admin\'s email'

        elif form_data['admin'] == 'not-sure':
            status_msg = ' '.join([
                'You can submit hours for review by organization admin\'s registered on openCurrents.',
                'You can also invite new admins to the platform.'
            ])
            return False, status_msg

    def create_approval_request(self, orgid, usertimelog, admin_id):
        # save admin-specific request for approval of hours
        actiontimelog = AdminActionUserTime(
            user_id=admin_id,
            usertimelog=usertimelog,
            action_type='req'
        )
        actiontimelog.save()

        return True

    def invite_new_admin(self, org, admin_email, admin_name):
        user_new = None
        doInvite = False
        try:
            user_new = User.objects.get(username = admin_email)
            doInvite = not user_new.has_usable_password()
        except User.DoesNotExist:
            # user_new = User(
            #     username=admin_email,
            #     email=admin_email,
            #     first_name=admin_name
            # )
            # user_new.save()
            doInvite = True

        if doInvite:
            try:
                sendTransactionalEmail(
                    'volunteer-invites-admin',
                    None,
                    [
                        {
                            'name': 'ADMIN_FNAME',
                            'content': admin_name
                        },
                        {
                            'name': 'FNAME',
                            'content': self.request.user.first_name
                        },
                        {
                            'name': 'LNAME',
                            'content': self.request.user.last_name
                        },
                        {
                            'name': 'EVENT',
                            'content': False
                        },
                        {
                            'name': 'ORG_NAME',
                            'content': org.name
                        },
                        {
                            'name': 'EMAIL',
                            'content': admin_email
                        }
                    ],
                    admin_email
                )
            except Exception as e:
                logger.error(
                    'unable to send transactional email: %s (%s)',
                    e.message,
                    type(e)
                )
        # try:
        #     org_user = OrgUser(
        #         org=org,
        #         user=user_new
        #     )
        #     org_user.save()
        # except Exception as e:
        #     logger.error(
        #         'Org user already present: %s (%s)',
        #         e.message,
        #         type(e)
        #     )

        try:
            sendTransactionalEmail(
                'new-admin-invited',
                None,
                [
                    {
                        'name': 'ORG_NAME',
                        'content': org.name
                    },
                    {
                        'name': 'ADMIN_NAME',
                        'content': admin_name
                    },
                    {
                        'name': 'ADMIN_EMAIL',
                        'content': admin_email
                    },
                    {
                        'name': 'FNAME',
                        'content': self.request.user.first_name
                    },
                    {
                        'name': 'LNAME',
                        'content': self.request.user.last_name
                    }
                ],
                'bizdev@opencurrents.com'
            )
        except Exception as e:
                logger.error(
                    'unable to send transactional email: %s (%s)',
                    e.message,
                    type(e)
                )
        return user_new


    def get_context_data(self, **kwargs):
        #Get the status msg from URL
        context = super(TimeTrackerView, self).get_context_data(**kwargs)
        userid = self.request.user.id
        try:
            usertimelog = UserTimeLog.objects.filter(user__id=userid).order_by('datetime_start').reverse()[0]
            actiontimelog = AdminActionUserTime.objects.filter(usertimelog = usertimelog)
            context['org_stat_id'] = actiontimelog[0].usertimelog.event.project.org.id
            context['status_msg'] = self.kwargs.pop('status_msg')
            if context['org_stat_id']==userid:
                context['org_stat_id'] = ''
            else:
                context['admin_name'] = actiontimelog[0].user.first_name+":"+actiontimelog[0].user.last_name
        except KeyError:
                pass
        except:
            context['org_stat_id'] = ''
        return context


    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        data = form.cleaned_data
        org = Org.objects.get(id=data['org'])
        tz = org.timezone

        status = self.track_hours(data)
        isValid = status[0]
        if isValid:
            # tracked time is valid
            return redirect('openCurrents:time-tracked')
        else:
            status_msg = None
            try:
                status_msg = status[1]
            except Exception:
                pass

            return redirect(
                'openCurrents:time-tracker',
                status_msg=status_msg
            )


class TimeTrackedView(TemplateView):
    template_name = 'time-tracked.html'


class VolunteerView(TemplateView):
    template_name = 'volunteer.html'


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
        if kwargs.has_key('app_hr') and kwargs['app_hr'] == '1':
            context['app_hr'] = 1
        else:
            context['app_hr'] = 0

        try:
            org_name = Org.objects.get(id=context['orgid']).name
            context['orgname'] = org_name
        except Org.DoesNotExist:
            pass

        # calculate user balance in currents
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

        context['user_balance'] = round(issued_total, 2)

        # upcoming events user is registered for
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


class AdminProfileView(OrgAdminPermissionMixin, SessionContextView, TemplateView):
    template_name = 'admin-profile.html'

    def get_context_data(self, **kwargs):
        context = super(AdminProfileView, self).get_context_data(**kwargs)
        userid = context['userid']
        admin_id = self.request.user.id
        orgid = context['orgid']
        org = Org.objects.get(pk=orgid)
        context['org_name'] = org.name
        context['timezone'] = org.timezone
        try:
            context['vols_approved'] = self.kwargs.pop('vols_approved')
            context['vols_declined'] = self.kwargs.pop('vols_declined')
        except KeyError:
            pass

        user = User.objects.get(id=userid)

        # find events created by admin that they have not been notified of
        new_events = Event.objects.filter(
            project__org__id=orgid
        ).filter(
            creator_id=userid
        ).filter(
            notified=False
        )
        num_events=len(new_events)
        context['num_events'] = num_events

        for event in new_events:
            event.notified=True
            event.save()

        # calculate total currents verified by admin's org
        verified_time = UserTimeLog.objects.filter(
            event__project__org__id=orgid
        ).filter(
            is_verified=True
        )

        org_event_user = dict([
            (event.id, set())
            for event in Event.objects.filter(project__org__id=orgid)
        ])

        issued_by_all = 0
        issued_by_admin = 0

        for timelog in verified_time:
            if not timelog.user.id in org_event_user[timelog.event.id]:
                org_event_user[timelog.event.id].add(timelog.user.id)
                event_hours = (timelog.event.datetime_end - timelog.event.datetime_start).total_seconds() / 3600
                issued_by_all += event_hours

                admin_approved_actions = timelog.adminactionusertime_set.filter(
                    user_id=admin_id,
                    action_type='app' 
                )
                if admin_approved_actions:
                    issued_by_admin += event_hours

        context['issued_by_all'] = round(issued_by_all, 2)
        context['issued_by_admin'] = round(issued_by_admin, 2)

        # past org events
        context['events_group_past'] = Event.objects.filter(
            event_type='GR',
            project__org__id=orgid,
            datetime_end__lte=datetime.now(tz=pytz.utc)
        ).order_by('-datetime_start')[:3]

        # current org events
        context['events_group_current'] = Event.objects.filter(
            event_type='GR',
            project__org__id=orgid,
            datetime_start__lte=datetime.now(tz=pytz.utc) + timedelta(hours=1),
            datetime_end__gte=datetime.now(tz=pytz.utc)
        )

        # upcoming org events
        context['events_group_upcoming'] = Event.objects.filter(
            event_type='GR',
            project__org__id=orgid,
            datetime_start__gte=datetime.now(tz=pytz.utc) + timedelta(hours=1)
        )

        userid = self.request.user.id
        org = OrgUserInfo(userid)
        orgid = org.get_org_id()
        projects = Project.objects.filter(org__id=orgid)
        events = Event.objects.filter(
            project__in=projects
        ).filter(
            event_type='MN'
        )

        # determine whether there are any unverified timelogs for admin
        usertimelogs = UserTimeLog.objects.filter(
            event__in=events
        ).filter(
            is_verified=False
        ).annotate(
            last_action_created=Max('adminactionusertime__date_created')
        )

        # admin-specific requests
        admin_requested_hours = AdminActionUserTime.objects.filter(
            user_id=userid
        ).filter(
            date_created__in=[
                utl.last_action_created for utl in usertimelogs
            ]
        ).filter(
            action_type='req'
        )

        # TODO: check for non-admin-specific requests that have not been deferred by admin

        context['user_time_log_status'] = admin_requested_hours.exists()

        return context


class EditProfileView(TemplateView):
    template_name = 'edit-profile.html'


class BlogView(TemplateView):
    template_name = 'Blog.html'


class CreateEventView(OrgAdminPermissionMixin, SessionContextView, FormView):
    template_name = 'create-event.html'
    form_class = ProjectCreateForm

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
            is_public=form_data['is_public'],
            datetime_start=form_data['datetime_start'],
            datetime_end=form_data['datetime_end'],
            coordinator_firstname=form_data['coordinator_firstname'],
            coordinator_email=form_data['coordinator_email'],
            creator_id = self.userid
        )
        event.save()

        try:
            orguser = OrgUserInfo(self.userid)
            coord_user = User.objects.get(email=form_data['coordinator_email'])
            if (coord_user.id != self.userid) and not OrgUserInfo(coord_user.id).get_orguser():
                #send an invite to join to org as admin
                try:
                    admin_user = User.objects.get(id=self.userid)
                    sendContactEmail(
                            'invite-admin',
                            None,
                            [
                                {
                                    'name': 'FNAME',
                                    'content': form_data['coordinator_firstname']
                                },
                                {
                                    'name': 'ADMIN_FNAME',
                                    'content': admin_user.first_name
                                },
                                {
                                    'name': 'ADMIN_LNAME',
                                    'content': admin_user.last_name
                                },
                                {
                                    'name': 'EVENT',
                                    'content': True
                                },
                                {
                                    'name': 'ORG_NAME',
                                    'content': Org.objects.get(id=self.orgid).name
                                },
                                {
                                    'name': 'DATE',
                                    'content': form_data['datetime_start'].date()
                                },
                                {
                                    'name': 'START_TIME',
                                    'content': form_data['datetime_start'].time()
                                },
                                {
                                    'name': 'END_TIME',
                                    'content': form_data['datetime_start'].time()
                                },
                                {
                                    'name': 'EMAIL',
                                    'content': form_data['coordinator_email']
                                }
                            ],
                            form_data['coordinator_email'],
                            admin_user.email
                        )
                except Exception as e:
                    logger.error(
                        'unable to send transactional email: %s (%s)',
                        e.message,
                        type(e)
                    )
        # if given coordinator_email does not exist
        except ObjectDoesNotExist:
            logger.debug('Coordinator does not exist')

        return event.id

    def _get_project_names(self):
        context = super(CreateEventView, self).get_context_data()
        orgid = context['org_id']
        self.orgid = orgid

        userid = context['userid']
        self.userid = userid

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
        form_data = form.cleaned_data
        if form_data['project_name'] in project_names:
            logger.info('event found')
            self.project = Project.objects.get(
                org__id=self.orgid,
                name=form_data['project_name']
            )
        else:
            self.project = None

        # create an event for each location
        event_ids = map(lambda loc: self._create_event(loc, form_data), locations)

        return redirect(
            'openCurrents:invite-volunteers',
            json.dumps(event_ids)
        )

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
        kwargs.update({'orgid': self.kwargs['org_id']})
        return kwargs


# needs to be implemented using UpdateView
class EditEventView(OrgAdminPermissionMixin, SessionContextView, TemplateView):
    template_name = 'edit-event.html'

    def get_context_data(self, **kwargs):
        context = super(EditEventView, self).get_context_data(**kwargs)
        # event
        org_user = OrgUserInfo(self.request.user.id)
        tz = org_user.get_org_timezone()
        event_id = kwargs.pop('event_id')
        event = Event.objects.get(id=event_id)
        context['event'] = event
        context['start_time'] = str(event.datetime_start.astimezone(pytz.timezone(tz)).time())
        context['end_time'] = str(event.datetime_end.astimezone(pytz.timezone(tz)).time())
        context['date_start'] = str(event.datetime_start.astimezone(pytz.timezone(tz)).date())
        return context

    def dispatch(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        event = Event.objects.get(id=event_id)
        if timezone.now() > event.datetime_end:
            return redirect('openCurrents:admin-profile')
        else:
            return super(EditEventView, self).dispatch(request, *args, **kwargs)

    def post(self, request, **kwargs):
        utc=pytz.UTC
        event_id = kwargs.pop('event_id')
        edit_event = Event.objects.get(id=event_id)

        # save button - needs to handled through forms
        post_data = self.request.POST
        if 'save-button' in post_data:
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
            org_user = OrgUserInfo(self.request.user.id)
            tz = org_user.get_org_timezone()

            edit_event.description = str(post_data['project-description'])
            edit_event.location = str(post_data['project-location-1'])
            edit_event.coordinator_firstname = str(post_data['coordinator-name'])
            edit_event.coordinator_email = str(post_data['coordinator-email'])
            edit_event.datetime_start = datetime.combine(datetime.strptime(post_data['project-date'], '%Y-%m-%d'),\
                datetime.strptime(str(post_data['project-start']),'%H:%M%p').time())
            edit_event.datetime_end = datetime.combine(datetime.strptime(post_data['project-date'], '%Y-%m-%d'),\
                datetime.strptime(str(post_data['project-end']),'%H:%M%p').time())

            # needs to be handled using forms
            if post_data['event-privacy'] == '1':
                edit_event.is_public = True
            elif post_data['event-privacy'] == '2':
                edit_event.is_public = False
            edit_event.save()

            coord_user = None
            coord_email = post_data['coordinator-email']
            try:
                coord_user = User.objects.get(email=coord_email)
            except User.DoesNotExist:
                logger.info(
                    "coordinator_email %s does not exist",
                    coord_email
                )

            if coord_user and coord_user.id != self.request.user.id and not OrgUserInfo(coord_user.id).get_orguser():
                #send an invite to join to org as admin
                try:
                    sendContactEmail(
                        'invite-admin',
                        None,
                        [
                            {
                                'name': 'FNAME',
                                'content': str(post_data['coordinator-name'])
                            },
                            {
                                'name': 'ADMIN_FNAME',
                                'content': self.request.user.first_name
                            },
                            {
                                'name': 'ADMIN_LNAME',
                                'content': self.request.user.last_name
                            },
                            {
                                'name': 'EVENT',
                                'content': True
                            },
                            {
                                'name': 'ORG_NAME',
                                'content': Organisation
                            },
                            {
                                'name': 'DATE',
                                'content': str(post_data['project-date'])
                            },
                            {
                                'name': 'START_TIME',
                                'content': str(post_data['project-start'])
                            },
                            {
                                'name': 'END_TIME',
                                'content': str(post_data['project-end'])
                            },
                            {
                                'name': 'EMAIL',
                                'content': coord_email
                            }
                        ],
                        coord_email,
                        self.request.user.email
                    )
                except Exception as e:
                    logger.error(
                        'unable to send transactional email: %s (%s)',
                        e.message,
                        type(e)
                    )

            project = Project.objects.get(id = edit_event.project.id)
            project.name = str(post_data['project-name'])
            project.save()
        elif 'del-button' in post_data:
            # user hit delete button
            # needs to be handled using forms
            edit_event.delete()

        return redirect('openCurrents:admin-profile')


# TODO: prioritize view by projects which user was invited to
class UpcomingEventsView(LoginRequiredMixin, SessionContextView, ListView):
    template_name = 'upcoming-events.html'
    context_object_name = 'events'

    def get_queryset(self):
        # show all public events plus private event for orgs the user is admin for
        userid = self.request.user.id

        # fetch orguser records
        orguser_recs = OrgUser.objects.filter(user__id=userid)
        orgs = [rec.org for rec in orguser_recs]

        # list of org admin group names
        org_admin_group_names = [
            '_'.join(['admin', str(org.id)])
            for org in orgs
        ]

        # list of org admin groups
        org_admin_groups = Group.objects.filter(
            name__in=org_admin_group_names,
            user__id=userid
        )

        # admin's org ids
        admin_org_ids = [
            group.name.split('_')[1]
            for group in org_admin_groups
        ]

        return Event.objects.filter(
            datetime_end__gte=datetime.now()
        ).filter(
            Q(is_public=True) | Q(is_public=False, project__org__id__in=admin_org_ids)
        )


class ProjectDetailsView(TemplateView):
    template_name = 'project-details.html'


class InviteVolunteersView(OrgAdminPermissionMixin, SessionContextView, TemplateView):
    template_name = 'invite-volunteers.html'

    def get_context_data(self, **kwargs):
        # skip context param determines whether we show skip button or not
        context = super(InviteVolunteersView, self).get_context_data(**kwargs)
        userid = self.request.user.id
        context['userid'] = userid
        context['skip'] = 0
        try:
            event_ids = kwargs.pop('event_ids')
            if event_ids:
                event = Event.objects.filter(
                    id__in=json.loads(event_ids)
                ).first()
                if not event:
                    raise KeyError
                context['event_project_name'] = event.project.name
                context['skip'] = 1
        except KeyError:
            context['skip'] = 0

        return context


    def post(self, request, *args, **kwargs):
        userid = self.request.user.id
        user = User.objects.get(id=userid)
        post_data = self.request.POST
        event_create_id = None
        try:
            event_create_id = json.loads(kwargs.pop('event_ids'))
        except:
            pass

        k = []
        k_old = []
        users = User.objects.values_list('username')
        user_list = [str(''.join(j)) for j in users]

        OrgUsers = OrgUserInfo(self.request.user.id)
        if OrgUsers:
            Organisation = OrgUsers.get_org_name()
        if post_data['bulk-vol'].encode('ascii','ignore') == '':
            num_vols = int(post_data['count-vol'])
        else:
            bulk_list = re.split(',| |\n',post_data['bulk-vol'])
            num_vols = len(bulk_list)
        for i in range(num_vols):
            if post_data['bulk-vol'].encode('ascii','ignore') == '':
                email_list = post_data['vol-email-'+str(i+1)]
                if email_list != '':
                    if email_list not in user_list:
                        k.append({"email":email_list, "name":post_data['vol-name-'+str(i+1)],"type":"to"})
                    elif email_list in user_list:
                        k_old.append({"email":email_list, "name":post_data['vol-name-'+str(i+1)],"type":"to"})
                    user_new = None
                    try:
                        user_new = User(
                            username=email_list,
                            email=email_list
                        )
                        user_new.save()
                    except Exception as e:
                        user_new = User.objects.get(username=email_list)

                    if user_new and event_create_id:
                        try:
                            multiple_event_reg = Event.objects.filter(id__in=event_create_id)
                            for i in multiple_event_reg:
                                user_event_registration = UserEventRegistration(
                                    user=user_new,
                                    event=i,
                                    is_confirmed=True
                                )
                                user_event_registration.save()
                        except Exception as e:
                            logger.error('unable to register user for event')
                else:
                    num_vols -= 1
            elif post_data['bulk-vol'] != '':
                user_email = str(bulk_list[i].strip())
                if str(bulk_list[i].strip()) != '' and bulk_list[i].strip() not in user_list:
                    k.append({"email":user_email, "type":"to"})
                elif bulk_list[i].strip() in user_list:
                    k_old.append({"email":user_email, "type":"to"})
                user_new = None
                try:
                    user_new = User(
                        username=user_email,
                        email=user_email
                    )
                    user_new.save()
                except Exception as e:
                    user_new = User.objects.get(username=user_email)

                if user_new and event_create_id:
                    try:
                        multiple_event_reg = Event.objects.filter(id__in=event_create_id)
                        for i in multiple_event_reg:
                            user_event_registration = UserEventRegistration(
                                user=user_new,
                                event=i,
                                is_confirmed=True
                            )
                            user_event_registration.save()
                    except Exception as e:
                        logger.error('unable to register user for event')
        try:
            event=Event.objects.get(id=event_create_id[0])
            events = Event.objects.filter(id__in=event_create_id)
            loc = [str(i.location).split(',')[0] for i in events]
            email_template_merge_vars = [
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
            ]
            try:
                tz = event.project.org.timezone
                if k:
                    sendBulkEmail(
                        'invite-volunteer-event-new',
                        None,
                        email_template_merge_vars,
                        k,
                        user.email
                    )
                if k_old:
                    sendBulkEmail(
                        'invite-volunteer-event-existing',
                        None,
                        email_template_merge_vars,
                        k_old,
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

        return redirect('openCurrents:admin-profile', num_vols)


class EventCreatedView(TemplateView):
    template_name = 'event-created.html'


class EventDetailView(LoginRequiredMixin, SessionContextView, DetailView):
    model = Event
    context_object_name = 'event'
    template_name = 'event-detail.html'

    def get_context_data(self, **kwargs):
        context = super(EventDetailView, self).get_context_data(**kwargs)
        context['form'] = EventRegisterForm()

        orguser = OrgUserInfo(self.request.user.id)

        # determine whether the user has already registered for the event
        is_registered = UserEventRegistration.objects.filter(
            user__id=self.request.user.id,
            event__id=context['event'].id,
            is_confirmed=True
        ).exists()

        # check if admin for the event's org
        is_org_admin=orguser.is_org_admin(context['event'].project.org.id)

        # check if event coordinator
        is_coord = Event.objects.filter(id=context['event'].id,coordinator_email=self.request.user.email).exists()

        context['is_registered'] = is_registered
        context['admin'] = is_org_admin
        context['coordinator'] = is_coord
 
        # list of confirmed registered users 
        context['registrants'] = ''
        if is_coord or is_org_admin:
            reg_list = []
            reg_list_names = []
            reg_objects = UserEventRegistration.objects.filter(event__id=context['event'].id, is_confirmed=True)
            
            for reg in reg_objects: 
                reg_list.append(str(reg.user.email))
                 
            context['registrants'] = reg_list

            for email in reg_list:
                reg_list_names.append( str(User.objects.get(email=email).first_name + " " + User.objects.get(email=email).last_name))
 
            context['registrants_names'] = reg_list_names

        return context


class LiveDashboardView(OrgAdminPermissionMixin, SessionContextView, TemplateView):
    template_name = 'live-dashboard.html'

    def dispatch(self, *args, **kwargs):
        try:
            event_id = kwargs.get('event_id')
            event = Event.objects.get(id=event_id)
            return super(LiveDashboardView, self).dispatch(*args, **kwargs)
        except Event.DoesNotExist:
            return redirect('openCurrents:404')

    def get_context_data(self, **kwargs):
        context = super(LiveDashboardView, self).get_context_data(**kwargs)
        context['form'] = UserSignupForm()

        # event
        event_id = kwargs.pop('event_id')
        event = Event.objects.get(id=event_id)
        context['event'] = event

        # disable checkin if event is too far in future
        if event.datetime_start > datetime.now(tz=pytz.UTC) + timedelta(minutes=15):
            context['checkin_disabled'] = True
        else:
            context['checkin_disabled'] = False

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
    admin_id = request.user.id

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
                admin_id
            )

            return HttpResponse(status=404)

        clogger = logger.getChild(
            'user %s; event %s' % (userid, event.project.name)
        )

        if checkin:
            # volunteer checkin
            usertimelog = UserTimeLog(
                user=User.objects.get(id=userid),
                event=event,
                is_verified=True,
                datetime_start=datetime.now(tz=pytz.UTC)
            )
            usertimelog.save()

            # admin action record
            actiontimelog = AdminActionUserTime(
                user_id=admin_id,
                usertimelog=usertimelog,
                action_type='app'
            )
            actiontimelog.save()

            clogger.info(
                'at %s: checkin',
                str(usertimelog.datetime_start)
            )

            # credit admin/coordinator only if not already done
            if not UserTimeLog.objects.filter(event__id=event.id, user__id=request.user.id):
                usertimelog = UserTimeLog(
                    user=User.objects.get(id=request.user.id),
                    event=event,
                    is_verified=True,                    
                    datetime_start=datetime.now(tz=pytz.UTC)
                )
                usertimelog.save()

                # admin action record
                actiontimelog = AdminActionUserTime(
                    user_id=admin_id,
                    usertimelog=usertimelog,
                    action_type='app'
                )
                actiontimelog.save()

            return HttpResponse(status=201)
        else:
            # volunteer checkout
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
        return HttpResponse(status=400)


@login_required
def event_register(request, pk):
    event = Event.objects.get(id=pk)
    form = EventRegisterForm(request.POST)

    # validate form data
    if form.is_valid():
        user = request.user
        message = form.cleaned_data['contact_message']

        #check for existing registration
        is_registered = UserEventRegistration.objects.filter(user__id=user.id, event__id=event.id, is_confirmed=True).exists()
        #check if the user is project coordinator
        is_coord = Event.objects.filter(id=event.id,coordinator_email=user.email).exists()

        #update is_confirmed=True or create new UserEventRegistration if needed
        if not is_coord and not is_registered:
            user_unregistered = UserEventRegistration.objects.filter(user__id=user.id, event__id=event.id, is_confirmed=False)
            if user_unregistered:
                #register the volunteer
                user_unregistered.update(is_confirmed=True)
            else:
                user_event_registration = UserEventRegistration(
                    user=user,
                    event=event,
                    is_confirmed=True
                )
                user_event_registration.save()

        coord_email = event.coordinator_email
        coord_user = User.objects.get(email=coord_email)
        coord_last_name = coord_user.last_name
        org_name = event.project.org.name


        # if an optional contact message was entered, send to project coordinator or registrants if user is_coord
        merge_var_list = [
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
                'name': 'ADMIN_LASTNAME',
                'content': coord_last_name
            },
            {
                'name': 'ORG_NAME',
                'content': org_name
            },
            {
                'name': 'ADMIN_EMAIL',
                'content': event.coordinator_email
            },
            {
                'name': 'DATE',
                'content': json.dumps(event.datetime_start,cls=DatetimeEncoder).replace('"','')
            },
            {
                'name': 'EVENT_ID',
                'content': event.id
            }
        ]
        if message:
            logger.info('User %s registered for event %s wants to send msg %s ', user.username, event.id, message)
            if is_coord:
                #contact all volunteers
                reg_list_uniques = []
                reg_list = UserEventRegistration.objects.filter(event__id=event.id, is_confirmed=True)
                
                for reg in reg_list: 
                    if(reg.user.email not in reg_list_uniques):
                        reg_list_uniques.append({"email":reg.user.email, "name":reg.user.first_name,"type":"to"})
                try:
                    merge_var_list.append({'name': 'MESSAGE','content': message})
                    sendBulkEmail(
                        'coordinator-messaged',
                        None,
                        merge_var_list,
                        reg_list_uniques,
                        user.email
                    )
                    email_template = ''
                except Exception as e:
                    logger.error(
                        'unable to send email: %s (%s)',
                        e,
                        type(e)
                    )
                    return redirect('openCurrents:500')
            elif is_registered:
                #message the coordinator as an already registered volunteer
                email_template = 'volunteer-messaged'
                merge_var_list.append({'name': 'MESSAGE','content': message})
                merge_var_list.append({'name': 'REGISTER','content': False})
            elif not is_registered:
                #message the coordinator as a new volunteer
                email_template = 'volunteer-messaged'
                merge_var_list.append({'name': 'MESSAGE','content': message})
                merge_var_list.append({'name': 'REGISTER','content': True})
        #if no message was entered and a new UserEventRegistration was created
        elif not is_registered and not is_coord:
            email_template = 'volunteer-registered'
            merge_var_list.append({'name': 'REGISTER','content': True})
            logger.info('User %s registered for event %s with no optional msg %s ', user.username, event.id, message)

        if email_template:
            try:
                sendContactEmail(
                    email_template,
                    None,
                    merge_var_list,
                    event.coordinator_email,
                    user.email
                )
            except Exception as e:
                logger.error(
                    'unable to send email: %s (%s)',
                    e.message,
                    type(e)
                )

        return redirect('openCurrents:registration-confirmed', event.id) #TODO add a redirect for coordinator who doesn't register
    else:
        logger.error('Invalid form: %s', form.errors.as_data())
        return redirect('openCurrents:event-detail', event.id)


@login_required
def event_register_live(request, eventid):
    userid = request.POST['userid']
    user = User.objects.get(id=userid)
    event = Event.objects.get(id=eventid)
    user_events = UserEventRegistration.objects.values('user__id','event__id').filter(user__id = userid).filter(event__id = eventid)
    if not user_events:
        user_event_registration = UserEventRegistration(
            user=user,
            event=event,
            is_confirmed=True
        )
        user_event_registration.save()
        logger.info('User %s registered for event %s', user.username, event.id)
    else:
        logger.info('User %s already registered for event %s', user.username, event.id)
        return HttpResponse(status=400)

    tz = event.project.org.timezone
    event_ds = event.datetime_start.time()
    event_de = event.datetime_end.time()
    d_now = datetime.utcnow()
    if d_now.time() < event_de and d_now.time() > event_ds and d_now.date() == event.datetime_start.date():
        event_status = '1'
    else:
        event_status = '0'
    return HttpResponse(content = json.dumps({'userid': userid, 'eventid': eventid, 'event_status': event_status}), status=201)


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


@login_required
def org_user_list(request, org_id):
    # return the list of admins for an org
    org_user = OrgUser.objects.filter(org__id=org_id)
    org_user_list = dict([
        (orguser.user.id, {
            'firstname': orguser.user.first_name,
            'lastname': orguser.user.last_name
        })
        for orguser in org_user
        # include current userid, instead disable it in select GUI
        #if orguser.user.id != request.user.id
    ])

    return HttpResponse(
        content = json.dumps(org_user_list),
        status=200
    )


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
                        )
                elif endpoint:
                    return HttpResponse(user.id, status=200)
                elif user.has_usable_password():
                    logger.info('user %s already verified', user_email)
                    return redirect(
                        'openCurrents:login',
                        status_msg='User with this email already exists'
                    )
            except:
                # if the above raised exception, why are we returning status 200?
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

                # Create and save a new group for admins of new org
                new_org_admins_group(org.id)

                org_user = OrgUser(
                    user=user,
                    org=org
                )
                org_user.save()
                sendTransactionalEmail(
                    'new-org-registered',
                    None,
                    [
                        {
                            'name': 'FNAME',
                            'content': user_firstname
                        },
                        {
                            'name': 'LNAME',
                            'content': user_firstname
                        },
                        {
                            'name': 'EMAIL',
                            'content': user_email
                        },
                        {
                            'name': 'ORG_NAME',
                            'content': org_name
                        },
                        {
                            'name': 'ORG_STATUS',
                            'content': request.POST['org_type']
                        }
                    ],
                    'bizdev@opencurrents.com'
                )
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
            if org_name:
                return redirect(
                   'openCurrents:check-email',
                   user_email,
                   1
                )
            else:
                return redirect(
                   'openCurrents:check-email',
                   user_email,
                )
                

    # fail with form validation error
    else:
        logger.error(
            'Invalid signup request: %s',
            form.errors.as_data()
        )

        # report the first validation error
        errors = [
            '%s: %s' % (field, error.messages[0])
            for field, le in form.errors.as_data().iteritems()
            for error in le
        ]

        if endpoint:
            return HttpResponse({errors: errors}, status=400)
        else:
            return redirect('openCurrents:signup', status_msg=errors[0])


def process_OrgNomination(request):
    form = OrgNominationForm(request.POST)

    if form.is_valid():
        org_name = form.cleaned_data['org_name']
        contact_name = form.cleaned_data['contact_name']
        contact_email = form.cleaned_data['contact_email']

        sendTransactionalEmail(
            'new-org-nominated',
            None,
            [
                {
                    'name': 'FNAME',
                    'content': request.user.first_name
                },
                {
                    'name': 'LNAME',
                    'content': request.user.last_name
                },
                {
                    'name': 'COORD_NAME',
                    'content': contact_name
                },
                {
                    'name': 'COORD_EMAIL',
                    'content': contact_email
                },
                {
                    'name': 'ORG_NAME',
                    'content': org_name
                }
            ],
            'bizdev@opencurrents.com'
                )

        return redirect('openCurrents:profile', status_msg='Thank you for nominating %s! We will reach out soon.' % org_name)

    return redirect('openCurrents:profile', status_msg="bad form!")

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
            userid = user.id
            org = OrgUser.objects.filter(user__id=userid)
            app_hr = 0
            if org:
                orgid = org[0].org.id
                projects = Project.objects.filter(org__id=orgid)
                events = Event.objects.filter(
                    project__in=projects
                ).filter(
                    event_type='MN'
                )

                # determine unverified time
                # we have exact same code in admin-profile - lets factor out into a function or class
                get_defer_times = AdminActionUserTime.objects.filter(user__id=userid)
                exclude_usertimelog = []
                timelogs = UserTimeLog.objects.filter(
                    event__in=events
                ).filter(
                    is_verified=False
                )
                for g_d_t in get_defer_times:
                    if g_d_t.usertimelog in timelogs:
                        exclude_usertimelog.append(g_d_t.usertimelog.event)
                timelogs = timelogs.exclude(event__in=exclude_usertimelog)
                today = date.today()
                if ((user.last_login.date())< today - timedelta(days=today.weekday()) and timelogs):
                    app_hr = json.dumps(1)
                else:
                    app_hr = json.dumps(0)

            login(request, user)
            try:
                # set the session var to keep the user logged in
                remember_me = request.POST['remember-me']
                request.session['profile'] = 'True'
            except KeyError:
                pass
            return redirect('openCurrents:profile', app_hr)
        else:
            return redirect('openCurrents:login', status_msg='Invalid login/password')
    else:
        logger.error(
            'Invalid login: %s',
            form.errors.as_data()
        )

        # report the first validation error
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

        return redirect('openCurrents:profile')

    #if form was invalid for bad password, still need to preserve token
    else:
        token = form.cleaned_data['verification_token']
        logger.error(
            'Invalid email confirmation request: %s',
            form.errors.as_data()
        )

        # report the first validation error
        errors = [
            error.messages[0]
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
        # report the first validation error
        errors = [
            error.messages[0]
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

        # report the first validation error
        errors = [
            error.messages[0]
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

            # Create and save a new group for admins of new org
            new_org_admins_group(org.id)

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

        # report the first validation error
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
