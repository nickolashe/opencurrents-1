from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.views.generic import View, ListView, TemplateView, DetailView, CreateView
from django.views.generic.edit import FormView
from django.contrib.auth.models import User, Group
from django.db import transaction, IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import F, Q, Max
from django.views.decorators.csrf import csrf_exempt,csrf_protect
from django.template.context_processors import csrf
from datetime import datetime, time, date
from collections import OrderedDict
from copy import deepcopy

from interfaces.auth import OcAuth
from interfaces.bizadmin import BizAdmin
from interfaces.orgadmin import OrgAdmin
from interfaces.ledger import OcLedger
from interfaces.ocuser import OcUser, UserExistsException, InvalidUserException
from interfaces.orgs import OcOrg, \
    OrgUserInfo, \
    OrgExistsException, \
    InvalidOrgUserException

import math
import re

from openCurrents import config
from openCurrents.models import \
    Org, \
    OrgUser, \
    Token, \
    Project, \
    Event, \
    UserEventRegistration, \
    UserSettings, \
    UserTimeLog, \
    AdminActionUserTime, \
    Item, \
    Offer, \
    Transaction, \
    TransactionAction

from openCurrents.forms import \
    UserSignupForm, \
    UserLoginForm, \
    EmailVerificationForm, \
    PasswordResetForm, \
    PasswordResetRequestForm, \
    OrgSignupForm, \
    CreateEventForm, \
    EditEventForm, \
    EventRegisterForm, \
    EventCheckinForm, \
    OrgNominationForm, \
    TimeTrackerForm, \
    OfferCreateForm, \
    OfferEditForm, \
    RedeemCurrentsForm


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
    def dispatch(self, request, *args, **kwargs):
        self.userid = request.user.id
        self.user = request.user

        # oc user
        self.ocuser = OcUser(self.userid)

        # user org
        orguserinfo = OrgUserInfo(request.user.id)
        self.org = orguserinfo.get_org()

        # org auth
        self.ocauth = OcAuth(self.userid)

        return super(SessionContextView, self).dispatch(
            request, *args, **kwargs
        )

    def get_context_data(self, **kwargs):
        context = super(SessionContextView, self).get_context_data(**kwargs)
        userid = self.request.user.id
        context['userid'] = userid

        # user org
        orguser = OrgUserInfo(userid)
        org = orguser.get_org()
        orgid = orguser.get_org_id()
        context['orgid'] = orgid
        context['org_id'] = orgid
        context['orgname'] = orguser.get_org_name()
        context['org_timezone'] = orguser.get_org_timezone()
        context['is_admin'] = self.ocauth.is_admin()
        context['is_admin_org'] = self.ocauth.is_admin_org()
        context['is_admin_biz'] = self.ocauth.is_admin_biz()

        return context


class BizSessionContextView(SessionContextView):
    def dispatch(self, request, *args, **kwargs):
        # biz admin user
        self.bizadmin = BizAdmin(request.user.id)

        return super(BizSessionContextView, self).dispatch(
            request, *args, **kwargs
        )

class OrgSessionContextView(SessionContextView):
    def dispatch(self, request, *args, **kwargs):
        # biz admin user
        self.orgadmin = OrgAdmin(request.user.id)

        return super(OrgSessionContextView, self).dispatch(
            request, *args, **kwargs
        )


class AdminPermissionMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        user = request.user

        # check if the user is logged in
        if not user.is_authenticated():
            return self.handle_no_permission()

        # try to obtain user => org mapping from url first
        # otherwise, default to user's org
        org_id = None
        try:
            org_id = kwargs['org_id']
        except KeyError:
            pass

        try:
            event_id = kwargs['event_id']
            event = Event.objects.get(id=event_id)
            org_id = event.project.org.id
        except KeyError, Event.DoesNotExist:
            pass

        # org auth
        self.ocauth = OcAuth(user.id)

        # check if user is in org admin group
        if not self.ocauth.is_admin(org_id):
            logger.warning(
                'insufficient permission for user %s',
                user.username
            )
            return redirect('openCurrents:403')

        # user has sufficient permissions
        return super(AdminPermissionMixin, self).dispatch(
            request, *args, **kwargs
        )


class OrgAdminPermissionMixin(AdminPermissionMixin):
    def dispatch(self, request, *args, **kwargs):
        userorgs = OrgUserInfo(self.request.user.id)
        org = userorgs.get_org()

        # check if user is an admin of an org
        if org.status != 'npf':
            logger.warning(
                'insufficient permission for user %s',
                request.user.username
            )
            return redirect('openCurrents:403')

        return super(OrgAdminPermissionMixin, self).dispatch(
            request, *args, **kwargs
        )


class BizAdminPermissionMixin(AdminPermissionMixin):
    def dispatch(self, request, *args, **kwargs):
        userorgs = OrgUserInfo(self.request.user.id)
        org = userorgs.get_org()

        # check if user is an admin of an org
        if org.status != 'biz':
            logger.warning(
                'insufficient permission for user %s',
                request.user.username
            )
            return redirect('openCurrents:403')

        return super(BizAdminPermissionMixin, self).dispatch(
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


class BizAdminView(BizAdminPermissionMixin, BizSessionContextView, TemplateView):
    template_name = 'biz-admin.html'

    def get_context_data(self, **kwargs):
        context = super(BizAdminView, self).get_context_data(**kwargs)

        # offers created by business
        offers = self.bizadmin.get_offers_all()
        context['offers'] = offers

        # list biz's pending offer redemption requests
        redeemed_pending = self.bizadmin.get_redemptions(status='pending')
        context['redeemed_pending'] = redeemed_pending

        # list biz's accepted offer redemption requests
        redeemed_approved = self.bizadmin.get_redemptions(status='approved')
        context['redeemed_approved'] = redeemed_approved

        # current balance
        currents_balance = self.bizadmin.get_balance_available()
        logger.info(currents_balance)
        context['currents_balance'] = currents_balance

        # pending currents balance
        currents_pending = self.bizadmin.get_balance_pending()
        context['currents_pending'] = currents_pending

        return context


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
        logger.info(requested_actions)
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
                week_num += 1
            else:
                break


        time_log = OrderedDict()
        items = {'Total': 0}

        for action in actions:
            user_timelog = action.usertimelog
            volunteer_user = user_timelog.user
            name = ' '.join([volunteer_user.first_name, volunteer_user.last_name])
            req_hours_bound_upper = timedelta(hours=24)
            req_hours_bound_lower = timedelta(minutes=15)
            req_hours = user_timelog.datetime_end - user_timelog.datetime_start

            # check upper/lower bounds for hours requested
            if req_hours < req_hours_bound_upper and req_hours >= req_hours_bound_lower:
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
                # ignore multi-day requests for now
                pass

        time_log = OrderedDict([
            (k, time_log[k])
            for k in time_log
            if time_log[k]['Total'] > 0
        ])
        logger.debug('approve-hours time_log: %s', time_log)

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

        if user:
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
        logger.debug('templist: %s', templist)

        admin_userid = self.request.user.id

        projects = Project.objects.filter(org__id=self.org.id)
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

            with transaction.atomic():
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

                        # issue currents for hours approved
                        OcLedger().issue_currents(
                            entity_id_from=self.org.orgentity.id,
                            entity_id_to=usertimelog.user.userentity.id,
                            amount=(usertimelog.datetime_end - usertimelog.datetime_start).total_seconds() / 3600
                        )

                    vols_approved += 1

                if action_type == 'dec':
                    vols_declined += 1

                # volunteer deferred
                # TODO: decide if we need to keep this
                elif action_type == 'def':
                    logger.warning('deferred timelog (legacy warning): %s', declined)

                # TODO: instead of updating the requests for approval,
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

        redirect_url = 'approve-hours' if admin_requested_hours else 'org-admin'

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


class InviteAdminsView(TemplateView):
    template_name = 'invite-admins.html'


class InventoryView(TemplateView):
    template_name = 'inventory.html'


class PublicRecordView(TemplateView):
    template_name = 'public-record.html'


class MarketplaceView(LoginRequiredMixin, SessionContextView, ListView):
    template_name = 'marketplace.html'
    context_object_name = 'offers'

    def get_queryset(self):
        return Offer.objects.all()

    def get_context_data(self, **kwargs):
        context = super(MarketplaceView, self).get_context_data(**kwargs)
        user_balance_available = OcLedger().get_balance(
            self.request.user.userentity.id
        )
        context['user_balance_available'] = user_balance_available

        return context


class MissionView(TemplateView):
    template_name = 'mission.html'


class MyHoursView(TemplateView):
    template_name = 'my-hours.html'


class NominateView(TemplateView):
    template_name = 'nominate.html'


class NominationConfirmedView(TemplateView):
    template_name = 'nomination-confirmed.html'


class NominationEmailView(TemplateView):
    template_name = 'nomination-email.html'


class NonprofitView(TemplateView):
    template_name = 'nonprofit.html'


class OrgHomeView(TemplateView):
    template_name = 'org-home.html'


class OrgSignupView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'org-signup.html'


class OurStoryView(TemplateView):
    template_name = 'our-story.html'


class RedeemCurrentsView(LoginRequiredMixin, SessionContextView, FormView):
    template_name = 'redeem-currents.html'
    form_class = RedeemCurrentsForm

    def dispatch(self, request, *args, **kwargs):
        offer_id = kwargs.get('offer_id')
        self.offer = Offer.objects.get(id=offer_id)
        self.userid = request.user.id

        user_balance_available = OcUser(self.userid).get_balance_available()
        logger.info(user_balance_available)
        if user_balance_available <= 0:
            # TODO: replace with a page explaining no sufficient funds
            return redirect(
                'openCurrents:marketplace',
                status_msg=' '.join([
                    'You need Currents to redeem an offer.',
                    '<a href="{% url "openCurrents:upcoming-events" %}">',
                    'Find a volunteer opportunity!</a>'
                ])
            )

        return super(RedeemCurrentsView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        logger.info(data['redeem_currents_amount'])

        transaction = Transaction(
            user=self.request.user,
            offer=self.offer,
            pop_image=data['redeem_receipt'],
            pop_no_proof=data['redeem_no_proof'],
            price_reported=data['redeem_price'],
            currents_amount=data['redeem_currents_amount']
        )

        if not data['redeem_receipt']:
            transaction.pop_type = 'oth'

        transaction.save()

        action = TransactionAction(
            transaction=transaction
        )
        action.save()

        logger.debug(
            'Transaction %d for offer %d was requested by userid %d',
            transaction.id,
            self.offer.id,
            self.request.user.id
        )

        return redirect(
            'openCurrents:profile',
            'We\'ve received your request for redeeming %s\'s offer' % self.offer.org.name
        )

    def get_context_data(self, **kwargs):
        context = super(RedeemCurrentsView, self).get_context_data(**kwargs)
        context['offer'] = Offer.objects.get(id=self.kwargs['offer_id'])

        return context

    def get_form_kwargs(self):
        """
        Passes offer id down to the redeem form.
        """
        kwargs = super(RedeemCurrentsView, self).get_form_kwargs()
        kwargs.update({'offer_id': self.kwargs['offer_id']})
        kwargs.update({'user': self.request.user})

        return kwargs


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
        userid = self.request.user.id

        if kwargs.get('app_hr') == '1':
            context['app_hr'] = 1
        else:
            context['app_hr'] = 0

        # verified currents balance
        balance_available = self.ocuser.get_balance_available()
        context['balance_available'] = format(round(balance_available, 2), '.2f')

        # pending currents balance
        balance_pending = self.ocuser.get_balance_pending()
        context['balance_pending'] = format(round(balance_pending, 2), '.2f')

        # available usd balance
        balance_available_usd = self.ocuser.get_balance_available_usd()
        context['balance_available_usd'] = format(
            round(balance_available_usd, 2),
            '.2f'
        )

        # pending usd balance
        balance_pending_usd = self.ocuser.get_balance_pending_usd()
        context['balance_pending_usd'] = format(
            round(balance_pending_usd, 2),
            '.2f'
        )

        # upcoming events user is registered for
        events_upcoming = self.ocuser.get_events_registered()
        context['events_upcoming'] = events_upcoming

        offers_redeemed = self.ocuser.get_offers_redeemed()
        context['offers_redeemed'] = offers_redeemed

        # hour requests
        hours_requested = self.ocuser.get_hours_requested()
        context['hours_requested'] = hours_requested

        hours_approved = self.ocuser.get_hours_approved()
        context['hours_approved'] = hours_approved

        # user timezone
        #context['timezone'] = self.request.user.account.timezone
        context['timezone'] = 'America/Chicago'

        return context


class OrgAdminView(OrgAdminPermissionMixin, OrgSessionContextView, TemplateView):
    template_name = 'org-admin.html'

    def get_context_data(self, **kwargs):
        context = super(OrgAdminView, self).get_context_data(**kwargs)
        context['timezone'] = self.org.timezone

        try:
            context['vols_approved'] = self.kwargs.pop('vols_approved')
            context['vols_declined'] = self.kwargs.pop('vols_declined')
        except KeyError:
            pass

        # find events created by admin that they have not been notified of
        new_events = Event.objects.filter(
            project__org__id=self.org.id
        ).filter(
            creator_id=self.user.id
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
            event__project__org__id=self.org.id
        ).filter(
            is_verified=True
        )

        org_event_user = dict([
            (event.id, set())
            for event in Event.objects.filter(project__org__id=self.org.id)
        ])

        issued_by_all = 0
        issued_by_admin = 0

        for timelog in verified_time:
            if not timelog.user.id in org_event_user[timelog.event.id]:
                org_event_user[timelog.event.id].add(timelog.user.id)
                event_hours = (timelog.event.datetime_end - timelog.event.datetime_start).total_seconds() / 3600
                issued_by_all += event_hours

                admin_approved_actions = timelog.adminactionusertime_set.filter(
                    user_id=self.user.id,
                    action_type='app'
                )
                if admin_approved_actions:
                    issued_by_admin += event_hours

        context['issued_by_all'] = round(issued_by_all, 2)
        context['issued_by_admin'] = round(issued_by_admin, 2)

        # past org events
        context['events_group_past'] = Event.objects.filter(
            event_type='GR',
            project__org__id=self.org.id,
            datetime_end__lte=datetime.now(tz=pytz.utc)
        ).order_by('-datetime_start')[:3]

        # current org events
        context['events_group_current'] = Event.objects.filter(
            event_type='GR',
            project__org__id=self.org.id,
            datetime_start__lte=datetime.now(tz=pytz.utc) + timedelta(hours=1),
            datetime_end__gte=datetime.now(tz=pytz.utc)
        )

        # upcoming org events
        context['events_group_upcoming'] = Event.objects.filter(
            event_type='GR',
            project__org__id=self.org.id,
            datetime_start__gte=datetime.now(tz=pytz.utc) + timedelta(hours=1)
        )

        hours_requested = self.orgadmin.get_hours_requested()
        context['hours_requested'] = hours_requested

        hours_approved = self.orgadmin.get_hours_approved()
        context['hours_approved'] = hours_approved

        context['has_hours_requested'] = hours_requested.exists()

        return context


class EditProfileView(TemplateView):
    template_name = 'edit-profile.html'


class BlogView(TemplateView):
    template_name = 'Blog.html'


class CreateEventView(OrgAdminPermissionMixin, SessionContextView, FormView):
    template_name = 'create-event.html'
    form_class = CreateEventForm

    def dispatch(self, request, *args, **kwargs):
        org_id = kwargs.get('org_id')
        self.org = Org.objects.get(id=org_id)
        return super(CreateEventView, self).dispatch(
            request, *args, **kwargs
        )


    def _create_event(self, location, form_data):
        if not self.project:
            project = Project(
                org=Org.objects.get(id=self.orgid),
                name=form_data['project_name']
            )
            project.save()
            self.project = project

        # admin user (event creator)
        admin_user = User.objects.get(id=self.userid)

        # coordinator user
        coord_user = User.objects.get(
            id=form_data['event_coordinator']
        )

        event = Event(
            project=self.project,
            description=form_data['event_description'],
            location=location,
            is_public=form_data['event_privacy'],
            datetime_start=form_data['datetime_start'],
            datetime_end=form_data['datetime_end'],
            coordinator=coord_user,
            creator_id = self.userid
        )
        event.save()

        if (coord_user.id != self.userid):
            # send an invite to coordinator
            # TODO (@danny):
            #   - is invite-admin the correct template to use, event for
            #     existing users?
            try:
                sendContactEmail(
                        'change-event-coordinator',
                        None,
                        [
                            {
                                'name': 'FNAME',
                                'content': coord_user.first_name
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
                                'content': self.org.name
                            },
                            {
                                'name': 'EVENT_NAME',
                                'content': event.project.name
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
                                'content': coord_user.email
                            }
                        ],
                        coord_user.email,
                        admin_user.email
                    )
            except Exception as e:
                logger.error(
                    'unable to send transactional email: %s (%s)',
                    e.message,
                    type(e)
                )
        else:
            logger.debug('admin is coordinator for event %d', event.id)

        return event.id

    def _get_project_names(self):
        '''
        this method fetches existing org's projects in order to
        provide it to form project name autocomplete
        '''
        projects = Project.objects.filter(org__id=self.org.id)
        project_names = [project.name for project in projects]

        return project_names

    def form_valid(self, form):
        '''
        method that's triggered when valid form data has posted, i.e.
        data passed validation in form's clean() method
            - location is handled in an ad-hoc manner because its
              a (variable length) list
        '''
        project_names = self._get_project_names()

        # submitted locations have names of the form 'event-location-$n',
        # where an n is a positive integer
        #   - need to use raw request.POST dictionary since no support for
        #     variable length lists
        locations = [
            val
            for (key, val) in self.request.POST.iteritems()
            if 'event-location' in key
        ]

        # form.cleaned_data contains validated form data
        form_data = form.cleaned_data

        # attempt to look up existing project based on provided project name
        if form_data['project_name'] in project_names:
            self.project = Project.objects.get(
                org__id=self.org.id,
                name=form_data['project_name']
            )
        else:
            self.project = None

        # create an event for each location
        # apply _create_event() to every location in locations list
        event_ids = map(lambda loc: self._create_event(loc, form_data), locations)

        return redirect(
            'openCurrents:invite-volunteers',
            json.dumps(event_ids)
        )

    def get_context_data(self, **kwargs):
        context = super(CreateEventView, self).get_context_data()

        project_names = self._get_project_names()
        context['project_names'] = mark_safe(json.dumps(project_names))

        return context

    def get_form_kwargs(self):
        '''
        pass down to (CreateEventForm) form for its internal use
            - orgid
            - userid
        '''
        kwargs = super(CreateEventView, self).get_form_kwargs()

        kwargs.update({'org_id': self.org.id})
        kwargs.update({'user_id': self.userid})

        return kwargs


# needs to be implemented using UpdateView
class EditEventView(CreateEventView):
    template_name = 'edit-event.html'
    form_class = EditEventForm

    def dispatch(self, request, *args, **kwargs):
        event_id = kwargs.pop('event_id')
        self.event = Event.objects.get(id=event_id)
        kwargs.update({'org_id': self.event.project.org.id})

        self.redirect_url = redirect('openCurrents:org-admin')

        if timezone.now() > self.event.datetime_end:
            return redirect('openCurrents:403')
        else:
            return super(EditEventView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        utc=pytz.UTC

        data = form.cleaned_data

        email_to_list = []

        # name change requires changing the project
        if self.event.project.name != data['project_name']:
            project = None
            try:
                project = Project.objects.get(
                    org__id=self.org.id,
                    name=data['project_name']
                )
                self.event.project = project
            except Project.DoesNotExist:
                self.event.project.name = data['project_name']

            self.event.project.save()
            self.event.save()

        # event detail changes
        if self.event.is_public != bool(data['event_privacy']) or \
            self.event.location != data['event_location'] or \
            self.event.description != data['event_description'] or \
            self.event.coordinator.id != int(data['event_coordinator']) or \
            self.event.datetime_start != data['datetime_start'] or \
            self.event.datetime_end != data['datetime_end']:

            userregs = UserEventRegistration.objects.filter(
                event__id=self.event.id,
                is_confirmed=True
            )
            volunteer_emails = [
                reg.user.email
                for reg in userregs
            ]

            for email in volunteer_emails:
                email_to_list.append({
                    'email': email,
                    'type': 'to'
                })

            try:
                sendBulkEmail(
                    'edit-event',
                    None,
                    [
                        {
                            'name': 'ADMIN_FIRSTNAME',
                            'content': self.user.first_name
                        },
                        {
                            'name': 'ADMIN_LASTNAME',
                            'content': self.user.last_name
                        },
                        {
                            'name': 'EVENT_TITLE',
                            'content': data['project_name']
                        },
                        {
                            'name': 'ORG_NAME',
                            'content': self.event.project.org.name
                        },
                        {
                            'name': 'EVENT_LOCATION',
                            'content': data['event_location']
                        },
                        {
                            'name': 'EVENT_DATE',
                            'content': data['event_date']
                        },
                        {
                            'name':'EVENT_START_TIME',
                            'content': data['event_starttime']
                        },
                        {
                            'name':'EVENT_END_TIME',
                            'content': data['event_endtime']
                        },
                        {
                            'name': 'TITLE',
                            'content': int(self.event.project.name != data['project_name'])
                        },
                        {
                            'name': 'LOCATION',
                            'content': int(self.event.location != data['event_location'])
                        },
                        {
                            'name':'TIME',
                            'content': int(
                                self.event.datetime_start != data['datetime_start'] or \
                                self.event.datetime_end != data['datetime_end']
                            )
                        },
                        {
                            'name': 'EVENT_ID',
                            'content': self.event.id
                        }

                    ],
                    email_to_list,
                    self.user.email
                )
            except Exception as e:
                logger.info(e)
                logger.error(
                    'unable to send email: %s (%s)',
                    e,
                    type(e)
                )
                return redirect('openCurrents:500')

            self.event.location = data['event_location']
            self.event.description = data['event_description']

            coord_user = User.objects.get(id=data['event_coordinator'])
            self.event.coordinator = coord_user
            self.event.datetime_start = data['datetime_start']
            self.event.datetime_end = data['datetime_end']
            self.event.is_public = data['event_privacy']

            self.event.save()

            self.redirect_url = redirect(
                'openCurrents:org-admin',
                status_msg='Event details have been updated'
            )

        return self.redirect_url

    def get_form_kwargs(self):
        '''
        Passes event and user ids down to the form
        '''
        kwargs = super(EditEventView, self).get_form_kwargs()
        kwargs.update({'event_id': self.event.id})
        kwargs.update({'user_id': self.userid})

        return kwargs


# TODO: prioritize view by projects which user was invited to
class UpcomingEventsView(LoginRequiredMixin, SessionContextView, ListView):
    template_name = 'upcoming-events.html'
    context_object_name = 'events'

    def get_context_data(self, **kwargs):
        # skip context param determines whether we show skip button or not
        context = super(UpcomingEventsView, self).get_context_data(**kwargs)
        #context['timezone'] = self.request.user.account.timezone
        context['timezone'] = 'America/Chicago'

        return context


    def get_queryset(self):
        # show all public events plus private event for orgs the user is admin for
        userid = self.request.user.id

        event_query_filter = Q(is_public=True)
        if self.ocauth.is_admin_org():
            event_query_filter |= Q(is_public=False, project__org__id=self.org.id)

        return Event.objects.filter(
            datetime_end__gte=datetime.now(tz=pytz.utc)
        ).filter(
            event_query_filter
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
            if type(json.loads(event_ids)) == list:
                pass
            else:
                event_ids = [int(event_ids)]
                event_ids = unicode(event_ids)
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
            event_create_id = kwargs.pop('event_ids')
            if type(json.loads(event_create_id)) == list:
                pass
            else:
                event_create_id = [int(event_create_id)]
                event_create_id = unicode(event_create_id)
            event_create_id = json.loads(event_create_id)
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
            tz = event.project.org.timezone
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

        return redirect('openCurrents:org-admin', num_vols)


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
        is_coord = Event.objects.filter(
            id=context['event'].id,
            coordinator__id=self.request.user.id
        ).exists()

        context['is_registered'] = is_registered
        context['admin'] = is_org_admin
        context['coordinator'] = is_coord

        # list of confirmed registered users
        context['registrants'] = []
        if is_coord or is_org_admin:
            reg_list = []
            reg_list_names = []
            reg_objects = UserEventRegistration.objects.filter(
                event__id=context['event'].id,
                is_confirmed=True
            )

            for reg in reg_objects:
                reg_list.append(reg.user.email)

            context['registrants'] = reg_list

            for email in reg_list:
                reg_user = User.objects.get(email=email)
                reg_list_names.append(
                    ' '.join([reg_user.first_name, reg_user.last_name])
                )

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


class OfferCreateView(LoginRequiredMixin, BizSessionContextView, FormView):
    template_name = 'offer.html'
    form_class = OfferCreateForm

    def form_valid(self, form):
        data = form.cleaned_data

        offer_item, was_created = Item.objects.get_or_create(name=data['offer_item'])

        offer = Offer(
            org=self.org,
            item=offer_item,
            currents_share=data['offer_current_share'],
        )

        if data['offer_limit_choice']:
            offer.limit = data['offer_limit_value']

        offer.save()

        logger.debug(
            'Offer for %d% on %s created by %s',
            data['offer_current_share'],
            offer_item.name,
            self.org.name
        )

        return redirect(
            'openCurrents:biz-admin',
            'Your offer for %s is now live!' % offer_item.name
        )


    def get_context_data(self, **kwargs):
        context = super(OfferCreateView, self).get_context_data(**kwargs)

        return context

    def get_form_kwargs(self):
        """
        Passes orgid down to the offer form.
        """
        kwargs = super(OfferCreateView, self).get_form_kwargs()
        kwargs.update({'orgid': self.org.id})

        return kwargs


class OfferEditView(OfferCreateView):
    template_name = 'edit-offer.html'
    form_class = OfferEditForm

    def dispatch(self, request, *args, **kwargs):
        # get existing ofer
        self.offer = Offer.objects.get(pk=kwargs.get('offer_id'))
        logger.info(self.offer)
        return super(OfferEditView, self).dispatch(
            request, *args, **kwargs
        )

    def form_valid(self, form):
        data = form.cleaned_data

        offer_item, was_created = Item.objects.get_or_create(name=data['offer_item'])

        self.offer.item = offer_item
        self.offer.currents_share = data['offer_current_share']

        logger.info(data)
        if data['offer_limit_choice']:
            self.offer.limit = data['offer_limit_value']
        else:
            self.offer.limit = -1

        self.offer.save()

        logger.debug(
            'Offer %d for %d%% on %s updated by %s',
            self.offer.id,
            int(data['offer_current_share']),
            offer_item.name,
            self.org.name
        )

        return redirect(
            'openCurrents:biz-admin',
            'Your offer for %s has been changed.' % offer_item.name
        )

    def get_context_data(self, **kwargs):
        context = super(OfferEditView, self).get_context_data()

        context['form'].fields['offer_current_share'].widget.attrs['value'] = self.offer.currents_share
        context['form'].fields['offer_item'].widget.attrs['value'] = self.offer.item.name

        limit = self.offer.limit
        context['form'].fields['offer_limit_choice'].initial = 0 if limit == -1 else 1

        if self.offer.limit != -1:
            context['form'].fields['offer_limit_value'].initial = limit

        return context


    def get_form_kwargs(self):
        """
        Passes offer id down to the offer form.
        """
        kwargs = super(OfferEditView, self).get_form_kwargs()
        kwargs.update({'offer_id': self.offer.id})

        return kwargs


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

        # check for existing registration
        is_registered = UserEventRegistration.objects.filter(user__id=user.id, event__id=event.id, is_confirmed=True).exists()

        # check if the user is project coordinator
        is_coord = Event.objects.filter(
            id=event.id,
            coordinator__id=user.id
        ).exists()

        # update is_confirmed=True or create new UserEventRegistration if needed
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
                'content': event.coordinator.first_name
            },
            {
                'name': 'ADMIN_LASTNAME',
                'content': event.coordinator.last_name
            },
            {
                'name': 'ORG_NAME',
                'content': org_name
            },
            {
                'name': 'ADMIN_EMAIL',
                'content': event.coordinator.email
            },
            {
                'name': 'DATE',
                'content': json.dumps(event.datetime_start,cls=DatetimeEncoder).replace('"','')
            },
            {
                'name': 'EVENT_NAME',
                'content': event.project.name
            },
            {
                'name': 'EVENT_ID',
                'content': event.id
            }
        ]

        email_template = None

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
        else:
            return redirect(
                'openCurrents:event-detail',
                pk=event.id,
                status_msg='Please enter a message'
            )

        if email_template:
            try:
                sendContactEmail(
                    email_template,
                    None,
                    merge_var_list,
                    event.coordinator.email,
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


def process_signup(
    request,
    referrer=None,
    endpoint=False,
    verify_email=True,
    mock_emails=False
):
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
        org_status = form.cleaned_data.get('org_status', '')
        org_admin_id = form.cleaned_data.get('org_admin_id', '')

        logger.debug('user %s sign up request', user_email)

        # try saving the user without password at this point
        user = None
        try:
            user = OcUser().setup_user(
                username=user_email,
                email=user_email,
                first_name=user_firstname,
                last_name=user_lastname
            )
        except UserExistsException:
            logger.debug('user %s already exists', user_email)

            user = User.objects.get(username=user_email)

            if not (user.first_name and user.last_name):
                user.first_name = user_firstname
                user.last_name = user_lastname
                user.save()

            if endpoint and not verify_email:
                return HttpResponse(user.id, status=200)

            elif user.has_usable_password():
                logger.info('user %s already verified', user_email)
                return redirect(
                    'openCurrents:login',
                    status_msg='User with this email already exists'
                )

        # user org
        if org_name:
            org = None
            try:
                org = OcOrg().setup_org(
                    name=org_name,
                    status=org_status
                )

                # Create and save a new group for admins of new org
                new_org_admins_group(org.id)

                org_user = OrgUserInfo(user.id).setup_orguser(org=org)

            except OrgExistsException:
                logger.warning('org %s already exists', org_name)
                redirect_url = {
                    'npf': 'nonprofit',
                    'biz': 'business'
                }
                return redirect(
                   'openCurrents:%s' % redirect_url[org_status],
                   'Organization named %s already exists!' % org_name
                )

            except InvalidOrgUserException as e:
                logger.error(
                    'unable to create orguser %s <=> %s',
                    org_name,
                    str(user.id)
                )
                return redirect('openCurrents:500')

            if not mock_emails:
                try:
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
                                'content': user_lastname
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
                except Exception as e:
                    logger.error(
                        'unable to send transactional email: %s (%s)',
                        e.message,
                        type(e)
                    )

        if verify_email:
            if not org_admin_id:
                logger.debug('Email verification requested')

                # generate and save token
                # TODO: refactor into a (token) interface
                token = uuid.uuid4()
                one_week_from_now = datetime.now(tz=pytz.utc) + timedelta(days=7)

                token_record = Token(
                    email=user_email,
                    token=token,
                    token_type='signup',
                    date_expires=one_week_from_now
                )

                token_record.save()

                if not mock_emails:
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
            else:
                logger.debug('User invited by admin %d', org_admin_id)
                admin_user = OcUser(org_admin_id).get_user()
                admin_org = OrgUserInfo(org_admin_id).get_org()

                if not mock_emails:
                    # send invite email
                    try:
                        sendTransactionalEmail(
                            'invite-volunteer',
                            None,
                            [
                                {
                                    'name': 'ADMIN_FIRSTNAME',
                                    'content': admin_user.first_name
                                },
                                {
                                    'name': 'ADMIN_LASTNAME',
                                    'content': admin_user.last_name
                                },
                                {
                                    'name': 'ORG_NAME',
                                    'content': admin_org.name
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

        # return
        if endpoint:
            return HttpResponse(user.id, status=201)
        else:
            if org_name:
                return redirect(
                   'openCurrents:check-email',
                   user_email,
                   org.id
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
                    'name': 'EMAIL',
                    'content': request.user.email
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

    return redirect(
        'openCurrents:time-tracker',
        status_msg='Organization name is required'
    )

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
            app_hr = 0
            today = date.today()

            # do a weekly check for unapproved requests (popup)
            if user.last_login.date() < today - timedelta(days=today.weekday()):
                try:
                    orgadmin = OrgAdmin(userid)
                    admin_requested_hours = orgadmin.get_hours_requested()

                    if admin_requested_hours:
                        app_hr = 1
                except Exception:
                    logger.debug(
                        'User %s is not org admin, no requested hours check',
                        userid
                    )

            login(request, user)
            try:
                # set the session var to keep the user logged in
                remember_me = request.POST['remember-me']
                request.session['profile'] = 'True'
            except KeyError:
                pass
            return redirect('openCurrents:profile', app_hr)
        else:
            return redirect('openCurrents:login', status_msg='Invalid login/password.')
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
        user_settings = UserSettings.objects.get(user__id=user.id)

        if form.cleaned_data['monthly_updates']:
            user_settings.monthly_updates = True;

        user_settings.save()

        logger.debug('verification of user %s is complete', user_email)

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
            status=form_data['org_status'],
            website=form_data['org_website']
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


@login_required
def get_user_balance_available(request):
    '''
    GET available balance for the logged in user
    TODO: convert to an API call for any user id
    '''
    balance = OcUser(request.user.id).get_balance_available()
    return HttpResponse(
        balance,
        status=200
    )

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
