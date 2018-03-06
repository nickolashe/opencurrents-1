from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.views.generic import View, ListView, TemplateView, DetailView, CreateView
from django.views.generic.edit import FormView, DeleteView
from django.contrib.auth.models import User, Group
from django.db import transaction, IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import F, Q, Max
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.template.context_processors import csrf
from django.utils.html import strip_tags
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

from openCurrents.interfaces import common
from openCurrents.interfaces.community import OcCommunity
from openCurrents.interfaces import convert

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
    TransactionAction, \
    Ledger

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
    BizDetailsForm, \
    OfferCreateForm, \
    OfferEditForm, \
    RedeemCurrentsForm, \
    PublicRecordsForm, \
    PopUpAnswer, \
    # HoursDetailsForm


from datetime import date, datetime, timedelta

import json
import mandrill
import logging
import pytz
import uuid
import decimal


logging.basicConfig(level=logging.DEBUG, filename='log/views.log')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Imports the Google Cloud client library
from google.cloud import logging as glogging
logging_client = glogging.Client()
glogger = logging_client.logger('oc-views')


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
        context['org'] = org
        context['orgid'] = orgid
        context['org_id'] = orgid
        context['orgname'] = orguser.get_org_name()
        context['org_timezone'] = orguser.get_org_timezone()
        context['is_admin'] = self.ocauth.is_admin()
        context['is_admin_org'] = self.ocauth.is_admin_org()
        context['is_admin_biz'] = self.ocauth.is_admin_biz()

        # workaround with status message for anything but TemplateView
        if 'status_msg' in self.kwargs and ('form' not in context or not context['form'].errors):
            context['status_msg'] = self.kwargs.get('status_msg', '')

        if 'msg_type' in self.kwargs:
            context['msg_type'] = self.kwargs.get('msg_type', '')

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


class SitemapView(TemplateView):
    template_name = 'sitemap.xml'


class RobotsView(TemplateView):
    template_name = 'robots.txt'


class HomeView(TemplateView):
    template_name = 'home.html'

    def dispatch(self, *args, **kwargs):
        try:
            # if there is session set for profile
            if self.request.session['profile']:
                return redirect('openCurrents:profile')
        except:
            # no session set
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


class BizAdminView(BizAdminPermissionMixin, BizSessionContextView, FormView):
    template_name = 'biz-admin.html'
    form_class = BizDetailsForm
    glogger_labels = {
        'handler': 'BizAdminView'
    }

    def get_context_data(self, **kwargs):
        context = super(BizAdminView, self).get_context_data(**kwargs)

        # offers created by business
        offers = self.bizadmin.get_offers_all()
        context['offers'] = offers

        # list biz's redemptions
        for status in ['pending', 'approved', 'redeemed']:
            context['redeemed_%s' % status] = self.bizadmin.get_redemptions(
                status=status
            )

        # current balance
        currents_balance = self.bizadmin.get_balance_available()
        context['currents_balance'] = currents_balance

        # pending currents balance
        currents_pending = self.bizadmin.get_balance_pending()
        context['currents_pending'] = currents_pending

        for field in context['form'].declared_fields.keys():
            val = getattr(self.org, field)
            if val:
                context['form'].fields[field].widget.attrs['value'] = val

        glogger_struct = {
            'msg': 'biz profile accessed',
            'username': self.user.email,
            'orgname': self.org.name
        }
        glogger.log_struct(glogger_struct, labels=glogger_labels)

        return context

    def form_valid(self, form):
        data = form.cleaned_data

        if all(i == '' for i in data.values()):
            return redirect(
                'openCurrents:biz-admin',
                status_msg='Please include at least one way for customers to contact you',
                msg_type='alert'
            )
        else:
            Org.objects.filter(id=self.org.id).update(
                website=data['website'],
                phone=data['phone'],
                email=data['email'],
                address=data['address'],
                intro=data['intro']
            )

            glogger_struct = {
                'msg': 'biz details updated',
                'username': self.user.email,
                'orgname': self.org.name
            }
            glogger.log_struct(glogger_struct, labels=glogger_labels)

            return redirect(
                'openCurrents:biz-admin',
                status_msg='Thank you for adding %s\'s details' % self.org.name
            )


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


class DeleteOfferView(BizAdminPermissionMixin, TemplateView):
    template_name = 'delete-offer.html'

    def post(self, request, *args, **kwargs):
        status_msg = 'Couldn\'t process the offer'
        msg_type = 'alert'

        if request.method == 'POST':
            try:
                offer_id = kwargs['pk']
                # mark the offer as inactive
                offer = Offer.objects.get(pk=offer_id)
                offer.is_active = False
                offer.save()

                status_msg = 'Offer \'{}\' has been removed'.format(offer)
                msg_type = ''
            except:
                logger.error('Couldn\'t process the offer {}'.format(offer))

        return redirect('openCurrents:biz-admin', status_msg, msg_type)


class LoginView(TemplateView):
    template_name = 'login.html'

    def get_context_data(self, **kwargs):
        context = super(LoginView, self).get_context_data(**kwargs)
        context['next'] = self.request.GET.get('next', None)
        return context


class InviteFriendsView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'invite-friends.html'


class ApproveHoursView(OrgAdminPermissionMixin, OrgSessionContextView, ListView):
    template_name = 'approve-hours.html'
    context_object_name = 'week'
    glogger_labels = {
        'handler': 'ApproveHoursView'
    }

    def get_context_data(self, **kwargs):
        context = super(ApproveHoursView, self).get_context_data(**kwargs)
        context['timezone'] = 'America/Chicago'

        return context

    def get_queryset(self, **kwargs):
        userid = self.request.user.id
        orguserinfo = OrgUserInfo(userid)
        orgid = orguserinfo.get_org_id()
        requested_actions = self.orgadmin.get_hours_requested()

        glogger_struct = {
            'msg': 'approve hours accessed',
            'admin': self.user.email,
            'hours_req_count': len(requested_actions)
        }
        glogger.log_struct(glogger_struct, labels=glogger_labels)

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

        # get the weeks timelog; week starting from 'week_startdate_monday'
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
                # week starting from 'week_startdate_monday'
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
                time_log[user_email]['name'] = name

                # time in hours rounded to nearest 15 min
                rounded_time = self.get_hours_rounded(user_timelog.datetime_start, user_timelog.datetime_end)

                # use day of week and date as key
                tz = orguserinfo.get_org_timezone()
                date_key = user_timelog.datetime_start.astimezone(pytz.timezone(tz)).strftime('%A, %m/%d')
                if date_key not in time_log[user_email]:
                    time_log[user_email][date_key] = [0]

                # add the time to the corresponding date_key and total
                st_time = user_timelog.datetime_start.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p')
                end_time = user_timelog.datetime_end.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p')
                time_log[user_email][date_key][0] += rounded_time
                time_log[user_email][date_key].append(st_time + ' - ' + end_time + ': ' + user_timelog.event.description)
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

        logger.debug('week %s', week)
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
        '''
        Takes request as input which is a comma separated string which is then split to form a list with data like
        ```['a@bc.com:1:7-20-2017','abc@gmail.com:0:7-22-2017',''...]```
        '''
        vols_approved = 0
        vols_declined = 0

        # TODO (@karbmk): see the comment below re: parsing raw request data
        post_data = self.request.POST['post-data']

        action_type_map = {
            0: 'dec',
            1: 'app',
            2: 'def'
        }

        # example list: ['a@bc.com:1:7-20-2017','abc@gmail.com:0:7-22-2017',''...]
        templist = post_data.split(',')
        logger.debug('templist: %s', templist)

        admin_userid = self.request.user.id

        projects = Project.objects.filter(org__id=self.org.id)
        events = Event.objects.filter(
            project__in=projects
        ).filter(
            event_type='MN'
        )

        for i in templist:
            '''
            eg for i:
            i.split(':')[0] = 'abc@gmail.com'
            i.split(':')[1] = '0' | '1'
            i.split(':')[2] = '7-31-2017'
            '''
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
            logger.debug('requested_actions: %s', requested_actions)

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
                            self.org.orgentity.id,
                            usertimelog.user.userentity.id,
                            action,
                            (usertimelog.datetime_end - usertimelog.datetime_start).total_seconds() / 3600
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
                    action.action_type = action_type
                    action.save()

                glogger_struct = {
                    'msg': 'approve hours posted',
                    'admin': self.user.email,
                    'req_actions_count': len(requested_actions),
                    'action': action_type
                }
                glogger.log_struct(glogger_struct, labels=glogger_labels)

        # lastly, determine if there any approval requests remaining for admin
        admin_requested_hours = self.orgadmin.get_hours_requested()
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


class FaqView(TemplateView):
    template_name = 'faq.html'


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


class HoursDetailView(LoginRequiredMixin, SessionContextView, ListView):
    template_name = 'hours-detail.html'
    model = AdminActionUserTime
    context_object_name = 'hours_detail'
    glogger_labels = {
        'handler': 'HoursDetailView'
    }

    def get_queryset(self):
        queryset = []
        self.userid = self.request.GET.get('user_id')
        self.hours_type = self.request.GET.get('type')
        self.is_admin = self.request.GET.get('is_admin')
        self.org_id = self.request.GET.get('org_id')

        if not self.userid or (self.hours_type not in ['pending', 'approved']):
            return redirect('openCurrents:404')

        try:
            self.user = User.objects.get(id=self.userid)
        except User.ObjectDoesNotExist:
            logger.warning('invalid user requested')
            return redirect('openCurrents:404')

        if self.is_admin == '1':
            user_instance = OrgAdmin(self.userid)
        else:
            user_instance = OcUser(self.userid)

        if self.hours_type == 'pending':
            queryset = user_instance.get_hours_requested()
        else:
            if self.org_id:
                queryset = user_instance.get_hours_approved(org_id=self.org_id)
            else:
                queryset = user_instance.get_hours_approved()

        if queryset:
            queryset = queryset.order_by('-usertimelog__event__datetime_start')

        return queryset

    def get_context_data(self, **kwargs):
        context = super(HoursDetailView, self).get_context_data(**kwargs)

        if self.is_admin == '1':
            context['hours_admin'] = True
            context['admin_name'] = ' '.join([
                self.user.first_name,
                self.user.last_name
            ])

        context['hours_type'] = self.hours_type
        context['timezone'] = 'America/Chicago'

        if self.org_id:
            org = OcOrg(self.org_id)
            context['hours_orgname'] = org.get_org_name()

        glogger_struct = {
            'msg': 'hours detail accessed',
            'username': self.user.email,
            'hours_userid': self.userid,
            'hours_type': self.hours_type,
            'is_admin': self.is_admin,
            'org_id': self.org_id
        }
        glogger.log_struct(glogger_struct, labels=glogger_labels)

        return context


class InviteAdminsView(TemplateView):
    template_name = 'invite-admins.html'


class InventoryView(TemplateView):
    template_name = 'inventory.html'


class PastEventsView(OrgAdminPermissionMixin, OrgSessionContextView, TemplateView):
    template_name = 'past-events.html'

    def get_context_data(self, **kwargs):
        context = super(PastEventsView, self).get_context_data(**kwargs)
        context['timezone'] = self.org.timezone

        # past org events
        context['events_group_past'] = Event.objects.filter(
            event_type='GR',
            project__org__id=self.org.id,
            datetime_end__lte=datetime.now(tz=pytz.utc)
        ).order_by('-datetime_start')

        return context


class PublicRecordView(LoginRequiredMixin, SessionContextView, TemplateView):
    template_name = 'public-record.html'
    glogger_labels = {
        'handler': 'PublicRecordView'
    }

    def get_top_list(self, entity_type='top-org', period='all-time'):
        glogger_struct = {
            'msg': 'public record accessed',
            'username': self.user.email,
            'record': entity_type,
            'period': period
        }
        glogger.log_struct(glogger_struct, labels=glogger_labels)

        if entity_type == 'top-org':
            return OcOrg().get_top_issued_npfs(period)
        elif entity_type == 'top-vol':
            return OcUser().get_top_received_users(period)
        elif entity_type == 'top-biz':
            return OcOrg().get_top_bizs(period)

    def get(self, request, *args, **kwargs):
        context = dict()

        form = PublicRecordsForm(request.GET or None)
        context['form'] = form
        if form.is_valid():
            context['entries'] = self.get_top_list(
                form.cleaned_data['record_type'],
                form.cleaned_data['period']
            )
        else:
            context['entries'] = self.get_top_list()

        return render(request, self.template_name, context)


class MarketplaceView(ListView):
    template_name = 'marketplace.html'
    context_object_name = 'offers'
    glogger_labels = {
        'handler': 'MarketplaceView'
    }

    def get_queryset(self):
        offers_all = OcUser().get_offers_marketplace()
        return offers_all

    def get_context_data(self, **kwargs):
        context = super(MarketplaceView, self).get_context_data(**kwargs)
        glogger_struct = {
            'msg': 'marketplace accessed',
        }

        if self.request.user.is_authenticated:
            user_balance_available = OcLedger().get_balance(
                self.request.user.userentity.id
            )
            glogger_struct['username'] = self.request.user.email
        else:
            glogger_struct['username'] = 'anonymous'
            user_balance_available = 0

        context['master_offer'] = Offer.objects.filter(is_master=True).first()
        context['user_balance_available'] = user_balance_available

        if 'status_msg' in self.kwargs and ('form' not in context or not context['form'].errors):
            context['status_msg'] = self.kwargs.get('status_msg', '')

        if 'msg_type' in self.kwargs:
            context['msg_type'] = self.kwargs.get('msg_type', '')

        glogger.log_struct(glogger_struct, labels=glogger_labels)

        return context


class MissionView(TemplateView):
    template_name = 'mission.html'


class MyHoursView(TemplateView):
    template_name = 'my-hours.html'


class NominateView(LoginRequiredMixin, SessionContextView, TemplateView):
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
    glogger_labels = {
        'handler': 'RedeemCurrentsView'
    }

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            offer_id = kwargs.get('offer_id')
            self.offer = Offer.objects.get(id=offer_id)
            self.userid = request.user.id
            self.ocuser = OcUser(self.userid)

            glogger_struct = {
                'msg': 'offer redemption request',
                'username': self.user.email,
                'offerid': self.offer.id
            }

            reqForbidden = False
            user_balance_available = self.ocuser.get_balance_available()
            user_master_offer_remaining = self.ocuser.get_master_offer_remaining()

            if user_balance_available <= 0:
                # TODO: replace with a page explaining no sufficient funds
                reqForbidden = True
                status_msg = ' '.join([
                    'You need Currents to redeem an offer.<br/>',
                    '<a href="/volunteer-opportunities/">',
                    'Find a volunteer opportunity!',
                    '</a>'
                ])
                msg_type = 'alert'
                glogger_struct['reject_reason'] = 'no currents available'

            if self.offer.is_master and user_master_offer_remaining <= 0:
                reqForbidden = True
                status_msg = ' '.join([
                    'You have already redeemed the maximum of',
                    str(common._MASTER_OFFER_LIMIT),
                    'Currents for this special offer.'
                ])
                msg_type = 'alert'
                glogger_struct['reject_reason'] = 'master offer limit reached'

            offer_num_redeemed = self.ocuser.get_offer_num_redeemed(self.offer)
            # logger.debug(offer_num_redeemed)

            offer_has_limit = self.offer.limit != -1
            offer_limit_exceeded = self.offer.limit - offer_num_redeemed <= 0
            if not reqForbidden and offer_has_limit and offer_limit_exceeded:
                reqForbidden = True
                status_msg = ' '.join([
                    'Vendor %s chose to set a limit',
                    'on the number of redemptions for %s this month'
                ]) % (self.offer.org.name, self.offer.item.name)
                msg_type = 'alert'
                glogger_struct['reject_reason'] = 'monthly offer limit reached'

            glogger.log_struct(glogger_struct, labels=glogger_labels)

            if reqForbidden:
                return redirect(
                    'openCurrents:marketplace',
                    status_msg,
                    msg_type
                )

        return super(RedeemCurrentsView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        # logger.info(data)

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

        if data['biz_name']:
            transaction.biz_name = data['biz_name']

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

        status_msg = 'You have submitted a request for approval by %s' % self.offer.org.name
        return redirect('openCurrents:profile', status_msg=status_msg)

    def get_context_data(self, **kwargs):
        context = super(RedeemCurrentsView, self).get_context_data(**kwargs)
        context['offer'] = Offer.objects.get(id=self.kwargs['offer_id'])
        context['cur_rate'] = convert._USDCUR
        context['tr_fee'] = int(convert._TR_FEE * 100)
        context['master_offer'] = Offer.objects.filter(is_master=True).first()
        context['master_funds_available'] = self.ocuser.get_master_offer_remaining()

        return context

    def get_form_kwargs(self):
        '''
        Passes offer id down to the redeem form.
        '''
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
    glogger_labels = {
        'handler': 'TimeTrackerView'
    }

    def track_hours(self, form_data):
        userid = self.request.user.id
        user = User.objects.get(id=userid)

        if form_data['org']:
            org = Org.objects.get(id=form_data['org'])
            tz = org.timezone
        else:
            tz = 'America/Chicago'

        # if the time is same or within the range of already existing tracking
        track_exists_1 = UserTimeLog.objects.filter(
            user=user
        ).filter(
            datetime_start__gte=form_data['datetime_start']
        ).filter(
            datetime_end__lte=form_data['datetime_end']
        )

        # if the time is same or Part of it where start time is earlier and end time is greater than end time
        track_exists_2 = UserTimeLog.objects.filter(
            user=user
        ).filter(
            datetime_start__lte=form_data['datetime_start']
        ).filter(
            datetime_end__gte=form_data['datetime_end']
        )

        # if the time is same or Part of it where start time is earlier and end time falls in the range
        track_exists_3 = UserTimeLog.objects.filter(
            user=user
        ).filter(
            datetime_start__lt=form_data['datetime_start']
        ).filter(
            datetime_end__lt=form_data['datetime_end']
        ).filter(
            datetime_end__gt=form_data['datetime_start']
        )

        # if the time is same or Part of it where start time is greater but within the end-time and end time doesn't matter
        track_exists_4 = UserTimeLog.objects.filter(
            user=user
        ).filter(
            datetime_start__gt=form_data['datetime_start']
        ).filter(
            datetime_end__gt=form_data['datetime_end']
        ).filter(
            datetime_start__lt=form_data['datetime_end']
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
                logger.debug(status_time)

                # return redirect('openCurrents:time-tracker', status_time)
                msg_type = 'alert'
                return False, status_time, msg_type

        # if existing org
        if form_data['org'].isdigit() and not form_data['new_org']:
            # logging hours for existing admin
            if form_data['admin'].isdigit():
                # create admin-specific approval request
                self.create_proj_event_utimelog(
                    user,
                    form_data['admin'],
                    org,
                    form_data['description'],
                    form_data['datetime_start'],
                    form_data['datetime_end']
                )

                glogger_struct = {
                    'msg': 'hours tracked',
                    'username': user.email,
                    'orgname': org.name,
                    'adminid': form_data['admin']
                }
                glogger.log_struct(glogger_struct, labels=glogger_labels)

                return True, None

            # logging hours for a new admin
            elif form_data['admin'] == 'other-admin':
                admin_name = form_data['new_admin_name']
                admin_email = form_data['new_admin_email']

                glogger_struct = {
                    'msg': 'hour tracking request (new admin)',
                    'username': user.email,
                    'orgname': org.name,
                    'admin_email': admin_email
                }
                glogger.log_struct(glogger_struct, labels=glogger_labels)

                if not admin_email:
                    # admin field should be populated
                    msg_type = 'alert'
                    return False, 'Please enter admin\'s email', msg_type
                else:
                    # check if ORG user exists and he is an active admin
                    try:
                        user_to_check = User.objects.get(email=admin_email)
                        is_admin = OrgUserInfo(user_to_check.id).is_user_in_org_group()
                    except:
                        is_admin = False

                    if OrgUser.objects.filter(user__email=admin_email).exists() and is_admin:
                        msg_type = 'alert'
                        return False, '{user} is already associated with another organization and cannot approve hours for {org}'.format(org=org.name, user=admin_email), msg_type

                    # if ORG user exists
                    elif OrgUser.objects.filter(user__email=admin_email).exists():

                        # checkig if he's not a biz admin
                        npf_user = OrgUser.objects.get(user__email=admin_email)

                        if npf_user.org.status == 'npf':
                            is_biz_admin = False

                        else:
                            is_biz_admin = True

                    # if ORG user doesn't exist
                    elif not OrgUser.objects.filter(user__email=admin_email).exists():
                        # finding a user in system
                        try:
                            npf_user = User.objects.get(username=admin_email)
                        except:
                            npf_user = None

                        if not npf_user:
                            # creating a new user
                            try:
                                npf_user = OcUser().setup_user(
                                    username=admin_email,
                                    email=admin_email,
                                    first_name=admin_name,
                                )

                            except UserExistsException:
                                logger.debug('Org user %s already exists', admin_email)

                        # setting up new NPF user
                        try:
                            OrgUserInfo(npf_user.id).setup_orguser(org)
                        except InvalidOrgUserException:
                            logger.debug('Cannot setup NPF user: %s', npf_user)
                            msg_type = 'alert'
                            return False, 'Couldn\'t setup NPF admin', msg_type

                        is_biz_admin = False

                    if is_biz_admin:
                        msg_type = 'alert'
                        return False, 'The user with provided email is an organization admin. You can also invite new admins to the platform.', msg_type
                    else:
                        # sending invitations
                        new_npf_admin_user = self.invite_new_admin(
                            org,
                            admin_email,
                            admin_name,
                            description=form_data['description'],
                            datetime_start=form_data['datetime_start'].strftime('%Y-%m-%d %H:%M:%S'),
                            datetime_end=form_data['datetime_end'].strftime('%Y-%m-%d %H:%M:%S'),
                            date=form_data['datetime_start'].strftime('%Y-%m-%d'),
                            start_time=form_data['datetime_start'].strftime('%H:%M:%S'),
                            end_time=form_data['datetime_end'].strftime('%H:%M:%S')
                        )

                        # now create DB records for logged time
                        self.create_proj_event_utimelog(
                            user,
                            npf_user.id,
                            org,
                            form_data['description'],
                            form_data['datetime_start'],
                            form_data['datetime_end']
                        )
                        return True, None

        # if logging for a new org
        elif form_data['new_org']:
            glogger_struct = {
                'msg': 'hour tracking request (new org)',
                'username': user.email,
                'orgname': form_data['new_org'],
                'admin': form_data['new_admin_email']
            }
            glogger.log_struct(glogger_struct, labels=glogger_labels)

            if form_data['new_admin_email']:
                org = form_data['new_org']
                admin_name = form_data['new_admin_name']
                admin_email = form_data['new_admin_email']

                if not admin_email:
                    # admin field should be populated
                    msg_type = 'alert'
                    return False, 'Please enter admin\'s email', msg_type
                else:
                    # check if ORG user exists and he is an active admin
                    try:
                        user_to_check = User.objects.get(email=admin_email)
                        is_admin = OrgUserInfo(user_to_check.id).is_user_in_org_group()
                    except:
                        is_admin = False

                    if User.objects.filter(email=admin_email).exists() and is_admin:
                        user_org = Org.objects.all().filter(orguser__user__email=admin_email)[0]
                        msg_type = 'alert'
                        return False, 'The coordinator is already affiliated with an existing organization.', msg_type
                    else:
                        # inviting new admin
                        new_npf_admin_user = self.invite_new_admin(
                            org,
                            admin_email,
                            admin_name,
                            description=form_data['description'],
                            datetime_start=form_data['datetime_start'].strftime('%Y-%m-%d %H:%M:%S'),
                            datetime_end=form_data['datetime_end'].strftime('%Y-%m-%d %H:%M:%S'),
                            date=form_data['datetime_start'].strftime('%Y-%m-%d'),
                            start_time=form_data['datetime_start'].strftime('%H:%M:%S'),
                            end_time=form_data['datetime_end'].strftime('%H:%M:%S'),
                            admin_template='volunteer-invites-org',  # using different template when time is logged for a new org
                            biz_template='new-org-invited'  # using different template when time is logged for a new org
                        )

                        # as of now, do not submit hours prior to admin registering
                        # self.create_approval_request(org.id,usertimelog,new_npf_admin_user)

                        return True, 'new-org'
            else:
                return False, 'Please enter admin\'s email'

        else:
            status_msg = ' '.join(['You need to enter organization name.'])
            msg_type = 'alert'
            return False, status_msg, msg_type

    def create_proj_event_utimelog(
        self,
        user,
        new_npf_user_id,
        org,
        event_descr,
        datetime_start,
        datetime_end
    ):
        '''
        user = user object
        new_npf_user_id = new NPF admin ID
        org = org object
        event_descr = string, eg form_data['description']
        datetime_start, datetime_start = datetime.datetime obj
        '''
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
            description=event_descr,
            event_type='MN',
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )
        event.save()

        usertimelog = UserTimeLog(
            user=user,
            event=event,
            datetime_start=datetime_start,
            datetime_end=datetime_end
        )
        usertimelog.save()
        self.create_approval_request(org.id, usertimelog, new_npf_user_id)

    def add_to_email_vars(self, email_var_list, new_var_name, new_var_value):
        '''
        adds kwargs passed to the email vars
        email_var_list - list of dictionaries
        new_var_name - string
        new_var_value - form_data['xxxx_xxxx']
        '''
        email_var_list.append({
            'name': new_var_name.upper(),
            'content': new_var_value
        })

    def create_approval_request(self, orgid, usertimelog, admin_id):
        # save admin-specific request for approval of hours
        actiontimelog = AdminActionUserTime(
            user_id=admin_id,
            usertimelog=usertimelog,
            action_type='req'
        )
        actiontimelog.save()

        return True

    def invite_new_admin(self, org, admin_email, admin_name, **kwargs):
        user_new = None
        doInvite = True

        # adding flag to not call Mandrill during unittests
        test_time_tracker_mode = self.request.POST.get('test_time_tracker_mode')

        # adapting function for sending org.name or form_data['new_org'] to new admin
        if isinstance(org, Org):
            org = org.name  # the Org instance was passed, using name
        else:
            org = org  # the sting was passed, using it as an org name

        email_vars = [
            {
                'name': 'ADMIN_NAME',
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
                'content': org
            },
            {
                'name': 'EMAIL',
                'content': admin_email
            },
        ]

        # adding kwargs to email vars
        if kwargs:
            for kw_key, kw_value in kwargs.iteritems():
                self.add_to_email_vars(email_vars, kw_key, kw_value)

        # selecting template for emails
        if 'admin_template' in kwargs.keys():
            admin_template = kwargs['admin_template']
        else:
            admin_template = 'volunteer-invites-admin'

        if 'biz_template' in kwargs.keys():
            biz_template = kwargs['biz_template']
        else:
            biz_template = 'new-admin-invited'

        self.request.session['admin_template'] = admin_template
        self.request.session['biz_template'] = biz_template

        if doInvite:
            try:
                sendTransactionalEmail(
                    admin_template,
                    None,
                    email_vars,
                    admin_email,
                    # marker for testing purpose
                    session=self.request.session,
                    marker='1',
                    test_time_tracker_mode=test_time_tracker_mode
                )
            except Exception as e:
                logger.error(
                    'unable to send transactional email: %s (%s)',
                    e.message,
                    type(e)
                )

        try:
            email_vars_transactional = [
                {
                    'name': 'ORG_NAME',
                    'content': org
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
                },
                {
                    'name': 'EMAIL',
                    'content': self.request.user.email
                },
            ]

            # adding kwargs to email vars
            if kwargs:
                for kw_key, kw_value in kwargs.iteritems():
                    self.add_to_email_vars(email_vars_transactional, kw_key, kw_value)

            sendTransactionalEmail(
                biz_template,
                None,
                email_vars_transactional,
                'bizdev@opencurrents.com',
                # marker for testing purpose
                session=self.request.session,
                marker='1',
                test_time_tracker_mode=test_time_tracker_mode
            )
        except Exception as e:
                logger.error(
                    'unable to send transactional email: %s (%s)',
                    e.message,
                    type(e)
                )
        return user_new

    def get_context_data(self, **kwargs):
        # get the status msg from URL
        context = super(TimeTrackerView, self).get_context_data(**kwargs)
        userid = self.userid

        try:
            usertimelog = UserTimeLog.objects.filter(user__id=userid).order_by('datetime_start').reverse()[0]
            actiontimelog = AdminActionUserTime.objects.filter(usertimelog=usertimelog)
            context['org_stat_id'] = actiontimelog[0].usertimelog.event.project.org.id

            if context['org_stat_id'] == userid:
                context['org_stat_id'] = ''
            else:
                context['admin_name'] = ':'.join([
                    actiontimelog[0].user.first_name,
                    actiontimelog[0].user.last_name
                ])
        except KeyError:
                pass
        except:
            context['org_stat_id'] = ''

        return context

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        data = form.cleaned_data
        # org = Org.objects.get(id=data['org'])
        # tz = org.timezone

        status = self.track_hours(data)
        isValid = status[0]
        if isValid:
            # tracked time is valid
            if status[1] == 'new-org':
                return redirect('openCurrents:time-tracked', new_org=1)
            else:
                return redirect('openCurrents:time-tracked')
        else:
            status_msg = None
            try:
                status_msg = status[1]
            except Exception:
                pass

            try:
                msg_type = status[2]
            except:
                msg_type = 'success'

            return redirect(
                'openCurrents:time-tracker',
                status_msg=status_msg,
                msg_type=msg_type
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


class ProfileView(LoginRequiredMixin, SessionContextView, FormView):
    template_name = 'profile.html'
    login_url = '/home'
    redirect_unauthenticated_users = True
    form_class = BizDetailsForm

    def get_context_data(self, **kwargs):
        context = super(ProfileView, self).get_context_data(**kwargs)
        userid = self.request.user.id

        if kwargs.get('app_hr') == '1':
            context['app_hr'] = 1
        else:
            context['app_hr'] = 0

        # verified currents balance
        context['balance_available'] = self.ocuser.get_balance_available()

        # pending currents balance
        context['balance_pending'] = self.ocuser.get_balance_pending()

        # available usd balance
        context['balance_available_usd'] = self.ocuser.get_balance_available_usd()

        # pending usd balance
        context['balance_pending_usd'] = self.ocuser.get_balance_pending_usd()

        # upcoming events user is registered for
        context['events_upcoming'] = self.ocuser.get_events_registered()

        # offers redeemed
        context['offers_redeemed'] = self.ocuser.get_offers_redeemed()

        # hour requests
        context['hours_requested'] = self.ocuser.get_hours_requested()

        # hour approved by organization
        context['hours_by_org'] = self.ocuser.get_hours_approved(**{'by_org': True})

        # user timezone
        # context['timezone'] = self.request.user.account.timezone
        context['timezone'] = 'America/Chicago'

        # getting issued currents
        context['currents_amount_total'] = OcCommunity().get_amount_currents_total()

        # getting active volunteers, do not set quantity to None to get all active volunteers;
        # otherwise set to desired number of volunteers to be displayed
        context['active_volunteers_total'] = OcCommunity().get_active_volunteers_total()

        # getting currents total (accepted + pending)
        context['biz_currents_total'] = OcCommunity().get_biz_currents_total()

        return context

    def form_valid(self, form):
        data = form.cleaned_data
        Org.objects.filter(id=self.org.id).update(
            website=data['website'],
            phone=data['phone'],
            email=data['email'],
            address=data['address'],
            intro=data['intro']
        )

        if all(i == '' for i in data.values()):
            return redirect(
                'openCurrents:biz-admin',
                status_msg='%s\'s details are blank, please add details' % self.org.name,
                msg_type='alert'
            )
        else:
            return redirect(
                'openCurrents:biz-admin',
                status_msg='Thank you for adding %s\'s details' % self.org.name
            )


class OrgAdminView(OrgAdminPermissionMixin, OrgSessionContextView, TemplateView):
    template_name = 'org-admin.html'
    glogger_labels = {
        'handler': 'OrgAdminView'
    }

    def _sorting_hours(self, admins_dict, user_id):
        '''
        Takes the list of dictionaries eg '{admin.user : time_pending_per_admin }' and currently logged in NPF admin user id,
        then finds and add currently logged NPF admin user to the beginning of the sorted by values list of
        dictionaries.
        Returns sorted by values list of dictionaries with hours for currently logged NPF admin as the first element.
        '''

        final_dict = OrderedDict()
        temp_dict = OrderedDict()

        if admins_dict:
            # getting user instance
            user = User.objects.get(id=user_id)
            if user in admins_dict.keys():
                final_dict[user] = admins_dict.pop(user)

            # sorting dict
            temp_dict = OrderedDict(sorted(
                admins_dict.items(),
                key=lambda d: d[1], reverse=True
            ))

            for i, v in temp_dict.iteritems():
                final_dict[i] = v
        else:
            final_dict

        return final_dict

    def get_context_data(self, **kwargs):
        context = super(OrgAdminView, self).get_context_data(**kwargs)
        context['timezone'] = self.org.timezone

        try:
            context['vols_approved'] = self.kwargs.pop('vols_approved')
            context['vols_declined'] = self.kwargs.pop('vols_declined')
        except KeyError:
            pass

        # getting all admins for organization
        context['org_admins'] = OcOrg(self.org.id).get_admins()

        # find events created by admin that they have not been notified of
        new_events = Event.objects.filter(
            project__org__id=self.org.id
        ).filter(
            creator_id=self.user.id
        ).filter(
            notified=False
        )
        num_events = len(new_events)
        context['num_events'] = num_events

        for event in new_events:
            event.notified = True
            event.save()

        # calculating pending hours for every NPF admin
        context['hours_pending_by_admin'] = {}

        for admin in context['org_admins']:
            total_hours_pending = OrgAdmin(admin.id).get_total_hours_pending()

            if total_hours_pending > 0:
                context['hours_pending_by_admin'][admin] = total_hours_pending

        logger.debug(context['hours_pending_by_admin'])

        # sorting the list of admins by # of pending hours descending and putting current admin at the beginning of the list
        context['hours_pending_by_admin'] = self._sorting_hours(context['hours_pending_by_admin'], self.user.id)

        # calculating approved hours for every NPF admin and total NPF Org hours tracked
        context['issued_by_admin'] = {}
        context['issued_by_logged_admin'] = context['issued_by_all'] = time_issued_by_logged_admin = 0

        for admin in context['org_admins']:
            admin_total_hours_issued = OrgAdmin(admin.id).get_total_hours_issued()
            # amount_issued_by_admin = {admin.id: admin_total_hours_issued}

            # adding to total approved hours
            context['issued_by_all'] += admin_total_hours_issued

            # adding to current admin's approved hours
            if admin.id == self.user.id:
                time_issued_by_logged_admin = admin_total_hours_issued

            if admin_total_hours_issued > 0:
                context['issued_by_admin'][admin] = admin_total_hours_issued

            context['issued_by_logged_admin'] = time_issued_by_logged_admin

        # sorting the list of admins by # of approved hours descending and putting current admin at the beginning of the list
        context['issued_by_admin'] = self._sorting_hours(context['issued_by_admin'], self.user.id)

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

        glogger_struct = {
            'msg': 'npf profile accessed',
            'username': self.user.email,
            'orgname': self.org.name
        }
        glogger.log_struct(glogger_struct, labels=glogger_labels)

        return context


class EditProfileView(LoginRequiredMixin, View):
    form_class = PopUpAnswer

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect('/profile/')

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        userid = self.request.user.id
        try:
            profile_settings_instance = UserSettings.objects.get(user=userid)
        except:
            logger.error('Cannot find UserSettings instance for {} user ID and save welcome popup answer.'.format(userid))
            return redirect(
                'openCurrents:profile',
                status_msg='There was a problem processing your response.<br/>Please contact us at <a href="mailto:team@opencurrents.com">team@opencurrents.com</a>',
                msg_type='alert'
            )

        if form.is_valid():
            if 'yes' in form.data:
                profile_settings_instance.popup_reaction = True
                profile_settings_instance.save()
            if 'no' in form.data:
                profile_settings_instance.popup_reaction = False
                profile_settings_instance.save()

        return HttpResponseRedirect('/profile/')


class BlogView(TemplateView):
    template_name = 'Blog.html'


class CreateEventView(OrgAdminPermissionMixin, SessionContextView, FormView):
    template_name = 'create-event.html'
    form_class = CreateEventForm
    glogger_labels = {
        'handler': 'CreateEventView'
    }

    def dispatch(self, request, *args, **kwargs):
        org_id = kwargs.get('org_id')
        self.org = Org.objects.get(id=org_id)
        return super(CreateEventView, self).dispatch(
            request, *args, **kwargs
        )

    def _create_event(self, location, form_data):
        if not self.project:
            project = Project(
                org=Org.objects.get(id=self.org.id),
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
            creator_id=self.userid
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

        glogger_struct = {
            'msg': 'new event(s) created',
            'admin': self.user.email,
            'orgname': self.org.name,
            'event_count': len(event_ids)
        }
        glogger.log_struct(glogger_struct, labels=glogger_labels)

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
        utc = pytz.UTC
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
        if int(self.event.is_public) != data['event_privacy'] or \
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
                            'name': 'EVENT_START_TIME',
                            'content': data['event_starttime']
                        },
                        {
                            'name': 'EVENT_END_TIME',
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
                            'name': 'TIME',
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
        # context['timezone'] = self.request.user.account.timezone
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


class VolunteerOpportunitiesView(LoginRequiredMixin, SessionContextView, ListView):
    template_name = 'volunteer-opportunities.html'
    context_object_name = 'events'

    def get_context_data(self, **kwargs):
        # skip context param determines whether we show skip button or not
        context = super(VolunteerOpportunitiesView, self).get_context_data(**kwargs)
        # context['timezone'] = self.request.user.account.timezone
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

    def email_parser(self, a_string):
        '''
        looks for an email address in a string and returns email string if valid
        '''
        # setting up pattern
        pattern = r'([a-zA-Z0-9_\-\.]+@[a-zA-Z0-9_\-\.]+\.[a-zA-Z]{2,5})'

        # setting up variables
        firstname = lastname = email1 = email2 = None

        from string import strip

        if re.search(pattern, a_string):
            matches = re.findall(pattern, a_string)
            for match in matches:
                if match != '':
                    email = strip(match)

                    return email
        else:
            return False

    def post(self, request, *args, **kwargs):
        userid = self.request.user.id
        user = User.objects.get(id=userid)
        post_data = self.request.POST
        event_create_id = None
        test_mode = post_data.get('test_mode')

        try:
            event_create_id = kwargs.pop('event_ids')
            if type(json.loads(event_create_id)) == list:
                pass
            else:
                event_create_id = [int(event_create_id)]
                event_create_id = unicode(event_create_id)
            event_create_id = json.loads(event_create_id)
        except Exception as e:
            logger.error('unable to process events IDs')

        k = []
        k_old = []

        users = User.objects.values_list('email')
        user_list = [str(''.join(j)).lower() for j in users]

        OrgUsers = OrgUserInfo(self.request.user.id)
        if OrgUsers:
            Organisation = OrgUsers.get_org_name()

        if post_data['bulk-vol'].encode('ascii', 'ignore') == '':
            num_vols = int(post_data['count-vol'])

        else:
            bulk_list_raw = re.split(',|\n|\s', post_data['bulk-vol'].lower())
            bulk_list = []
            for email_string in bulk_list_raw:
                email = self.email_parser(email_string)
                if email:
                    bulk_list.append(email)
            num_vols = len(bulk_list)

        for i in range(num_vols):

            # processing individual emails
            if post_data['bulk-vol'].encode('ascii', 'ignore') == '':
                email_list = post_data['vol-email-' + str(i + 1)].lower()

                if email_list != '':

                    user_new = None

                    if email_list not in user_list:
                        k.append({
                            'email': email_list,
                            'name': post_data['vol-name-' + str(i + 1)],
                            'type': 'to'
                        })

                        try:
                            user_new = OcUser().setup_user(
                                username=email_list,
                                first_name=post_data['vol-name-' + str(i + 1)],
                                email=email_list,
                            )
                        except UserExistsException:
                            user_new = User.objects.get(username=email_list)

                    elif email_list in user_list:
                        user_new = User.objects.get(email=email_list)

                        # if event-based invitation and user exists  w/o password
                        if event_create_id and not User.objects.get(email=email_list).has_usable_password():
                            k.append({
                                'email': email_list,
                                'name': post_data['vol-name-' + str(i + 1)],
                                'type': 'to'
                            })

                        # if event-based invitation and user exists with password
                        elif event_create_id and User.objects.get(email=email_list).has_usable_password():
                            k_old.append({
                                'email': email_list,
                                'name': post_data['vol-name-' + str(i + 1)],
                                'type': 'to'
                            })

                        # non-event-based invitation and user exists wo password
                        elif not event_create_id and not User.objects.get(email=email_list).has_usable_password():
                            k.append({
                                'email': email_list,
                                'name': post_data['vol-name-' + str(i + 1)],
                                'type': 'to'
                            })

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

            # processing emails from bulk field
            elif post_data['bulk-vol'] != '':

                # setting vars' default values in case we couldn't get all needed data from parsed email
                first_name = last_name = user_email = None
                try:
                    user_email = bulk_list[i]
                except:
                    logger.error('Unable to read from parsed email')

                # user_email = str(bulk_list[i].strip())

                user_new = None

                if user_email and user_email not in user_list:
                    k.append({'email': user_email, 'type': 'to'})

                    try:
                        user_new = OcUser().setup_user(
                            username=user_email,
                            email=user_email
                        )
                    except UserExistsException:
                        user_new = User.objects.get(username=user_email)

                elif user_email and user_email in user_list:
                    user_new = User.objects.get(email=user_email)

                    # if event-based invitation and user exists w/o password
                    if event_create_id and not User.objects.get(email=user_email).has_usable_password():
                        k.append({'email': user_email, 'type': 'to'})

                    # if event-based invitation and user exists with password
                    elif event_create_id and User.objects.get(email=user_email).has_usable_password():
                        k_old.append({'email': user_email, 'type': 'to'})

                    # non-event-based invitation and user exists wo password
                    elif not event_create_id and not User.objects.get(email=user_email).has_usable_password():
                        k.append({'email': user_email, 'type': 'to'})

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

        email_template_merge_vars = []

        if post_data['personal_message'] != '':
            email_template_merge_vars.append({
                'name': 'PERSONAL_MESSAGE',
                'content': post_data['personal_message']
            })

        try:
            # inviting volunteers (event-based)
            event = Event.objects.get(id=event_create_id[0])
            events = Event.objects.filter(id__in=event_create_id)
            loc = [str(i.location).split(',')[0] for i in events]
            tz = event.project.org.timezone
            email_template_merge_vars.extend([
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
                    'content': event.datetime_start.astimezone(pytz.timezone(tz)).date().strftime('%b %d, %Y')
                },
                {
                    'name': 'EVENT_START_TIME',
                    'content': event.datetime_start.astimezone(pytz.timezone(tz)).time().strftime('%I:%M %p')
                },
                {
                    'name': 'EVENT_END_TIME',
                    'content': event.datetime_end.astimezone(pytz.timezone(tz)).time().strftime('%I:%M %p')
                },
            ])

            try:
                if k:
                    sendBulkEmail(
                        'invite-volunteer-event-new',
                        None,
                        email_template_merge_vars,
                        k,
                        user.email,
                        session=self.request.session,
                        marker='1',
                        test_mode=test_mode
                    )
                if k_old:
                    sendBulkEmail(
                        'invite-volunteer-event-existing',
                        None,
                        email_template_merge_vars,
                        k_old,
                        user.email,
                        session=self.request.session,
                        marker='1',
                        test_mode=test_mode
                    )
            except Exception as e:
                logger.error(
                    'unable to send email: %s (%s)',
                    e,
                    type(e)
                )
        except Exception as e:
            try:
                # inviting volunteers (non-event-based)
                email_template_merge_vars.extend([
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
                    },
                ])

                # sending emails to the new users and existing users with no passw
                to_send = k + k_old

                if to_send:
                    sendBulkEmail(
                        'invite-volunteer',
                        None,
                        email_template_merge_vars,
                        to_send,
                        user.email,
                        session=self.request.session,
                        marker='1',
                        test_mode=test_mode
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
        is_org_admin = orguser.is_org_admin(context['event'].project.org.id)

        # check if event coordinator
        is_coord = Event.objects.filter(
            id=context['event'].id,
            coordinator__id=self.request.user.id
        ).exists()

        context['is_registered'] = is_registered
        context['admin'] = is_org_admin
        context['coordinator'] = is_coord

        # list of confirmed registered users
        if is_coord or is_org_admin:
            regs = UserEventRegistration.objects.filter(
                event__id=context['event'].id,
                is_confirmed=True
            )

            context['registrants'] = dict([
                (reg.user.email, {
                    'first_name': reg.user.first_name,
                    'last_name': reg.user.last_name
                })
                for reg in regs
            ])

        return context


class LiveDashboardView(OrgAdminPermissionMixin, SessionContextView, TemplateView):
    template_name = 'live-dashboard.html'
    glogger_labels = {
        'handler': 'LiveDashBoardView'
    }

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

        glogger_struct = {
            'admin': self.request.user.email,
            'eventid': event.id
        }

        # disable checkin if event is too far in future
        if event.datetime_start > datetime.now(tz=pytz.UTC) + timedelta(minutes=15):
            context['checkin_disabled'] = True
        else:
            context['checkin_disabled'] = False
        glogger_struct['checkin_disabled'] = context['checkin_disabled']

        # registered users
        user_regs = UserEventRegistration.objects.filter(event__id=event_id)
        registered_users = sorted(
            set([
                user_reg.user for user_reg in user_regs
            ]),
            key=lambda u: u.last_name
        )
        context['registered_users'] = registered_users
        glogger_struct['reg_users_count'] = len(registered_users)

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

        # include users checked in to the event
        context['checkedin_users'] = list(set(
            [ut.user.id for ut in usertimelogs]
        ))

        glogger_struct['checked_in_user_count'] = len(context['checkedin_users'])
        glogger.log_struct(glogger_struct, labels=glogger_labels)

        return context


class RegistrationConfirmedView(LoginRequiredMixin, SessionContextView, DetailView):
    model = Event
    context_object_name = 'event'
    template_name = 'registration-confirmed.html'

    def get_context_data(self, **kwargs):
        context = super(RegistrationConfirmedView, self).get_context_data(**kwargs)
        context['is_coordinator'] = self.object.coordinator == self.user

        return context


class AddVolunteersView(TemplateView):
    template_name = 'add-volunteers.html'


class OfferCreateView(LoginRequiredMixin, BizSessionContextView, FormView):
    template_name = 'offer.html'
    form_class = OfferCreateForm
    glogger_labels = {
        'handler': 'OfferCreateView'
    }

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
        glogger_struct = {
            'msg': 'new offer created',
            'username': self.request.user.email,
            'orgname': self.org.name,
            'offerid': offer.id
        }
        glogger.log_struct(glogger_struct, labels=glogger_labels)

        return redirect(
            'openCurrents:biz-admin',
            'Your offer for %s is now live!' % offer_item.name
        )

    def form_invalid(self, form):
        existing_item_err = form.errors.get('offer_item', '')

        if existing_item_err:
            return redirect(
                'openCurrents:biz-admin',
                status_msg=strip_tags(existing_item_err),
                msg_type='alert'
            )

        return super(OfferCreateView, self).form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super(OfferCreateView, self).get_context_data(**kwargs)
        context['cur_rate'] = convert._USDCUR
        context['tr_fee'] = convert._TR_FEE

        return context

    def get_form_kwargs(self):
        '''
        Passes orgid down to the offer form.
        '''
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
        '''
        Passes offer id down to the offer form.
        '''
        kwargs = super(OfferEditView, self).get_form_kwargs()
        kwargs.update({'offer_id': self.offer.id})

        return kwargs


@login_required
def event_checkin(request, pk):
    glogger_labels = {
        'handler': 'event_checkin'
    }

    form = EventCheckinForm(request.POST)
    admin_id = request.user.id
    admin_user = User.objects.get(id=admin_id)
    admin_org = OrgUserInfo(admin_id).get_org()

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
        glogger_struct = {
            'admin': admin_user.email,
            'username': user.email,
            'eventid': event.id,
            'event_startime': event.datetime_start.strftime('%m/%d/%Y %H:%M:%S')
        }

        # allow checkins only as early as 15 min before event
        if timezone.now() < event.datetime_start - timedelta(minutes=15):
            clogger.warning('checkin too early for event start time')
            glogger_struct['msg'] = 'checkin attempt prior to allowed time'
            glogger.log_struct(glogger_struct, labels=glogger_labels)

            return HttpResponse(content=json.dumps({}), status=400)

        event_duration = common.diffInHours(event.datetime_start, event.datetime_end)

        status = 200
        if checkin:
            # volunteer checkin
            vol_user = User.objects.get(id=userid)
            try:
                with transaction.atomic():
                    usertimelog = UserTimeLog.objects.create(
                        user=vol_user,
                        event=event,
                        is_verified=True,
                        datetime_start=datetime.now(tz=pytz.UTC)
                    )

                    # admin action record
                    adminaction = AdminActionUserTime.objects.create(
                        user_id=admin_id,
                        usertimelog=usertimelog,
                        action_type='app'
                    )

                    OcLedger().issue_currents(
                        admin_org.orgentity.id,
                        vol_user.userentity.id,
                        adminaction,
                        event_duration
                    )
                    clogger.debug(
                        '%s: user checkin',
                        usertimelog.datetime_start.strftime('%m/%d/%Y %H:%M:%S')
                    )
                    glogger_struct['msg'] = 'user checkin'
                    glogger.log_struct(glogger_struct, labels=glogger_labels)

                    status = 201
            except Exception as e:
                clogger.debug(e.message)
                clogger.debug('user already checked in')

            # check in admin/coordinator
            try:
                with transaction.atomic():
                    usertimelog = UserTimeLog.objects.create(
                        user=admin_user,
                        event=event,
                        is_verified=True,
                        datetime_start=datetime.now(tz=pytz.UTC)
                    )

                    # admin action record
                    adminaction = AdminActionUserTime.objects.create(
                        user_id=admin_id,
                        usertimelog=usertimelog,
                        action_type='app'
                    )

                    OcLedger().issue_currents(
                        admin_org.orgentity.id,
                        admin_user.userentity.id,
                        adminaction,
                        event_duration
                    )
                    status = 201
                    glogger_struct['msg'] = 'admin checkin'
                    glogger.log_struct(glogger_struct, labels=glogger_labels)

            except Exception as e:
                clogger.debug(
                    'event admin %s already checked in',
                    admin_user.email
                )
                return HttpResponse(content=json.dumps({}), status=status)

            return HttpResponse(content=json.dumps({}), status=status)

        else:
            # volunteer checkout
            usertimelog = UserTimeLog.objects.filter(
                event__id=pk,
                user__id=userid
            )

            if usertimelog:
                usertimelog = usertimelog.latest()
                if not usertimelog.datetime_end:
                    usertimelog.datetime_end = datetime.now(tz=pytz.utc)
                    usertimelog.save()
                    clogger.debug(
                        'user checkout',
                        usertimelog.datetime_end.strftime('%m/%d/%Y %H:%M:%S')
                    )
                    glogger_struct['msg'] = 'user checkout'
                    glogger.log_struct(glogger_struct, labels=glogger_labels)

                    return HttpResponse(
                        common.diffInMinutes(usertimelog.datetime_start, usertimelog.datetime_end),
                        status=201
                    )
                else:
                    clogger.debug('user has already been checked out before')
                    return HttpResponse(
                        content=json.dumps({}),
                        status=200
                    )
            else:
                clogger.error('invalid checkout (not checked in)')
                return HttpResponse(status=400)

    else:
        logger.error('Invalid form: %s', form.errors.as_data())
        return HttpResponse(status=400)


@login_required
def event_register(request, pk):
    glogger_labels = {
        'handler': 'event_register'
    }
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
                # register the volunteer
                user_unregistered.update(is_confirmed=True)
            else:
                user_event_registration = UserEventRegistration(
                    user=user,
                    event=event,
                    is_confirmed=True
                )
                user_event_registration.save()

            glogger_struct = {
                'msg': 'user event registration confirmed',
                'username': user.email,
                'eventid': event.id
            }
            glogger.log_struct(glogger_struct, labels=glogger_labels)

        org_name = event.project.org.name
        tz = event.project.org.timezone

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
                'name': 'START_TIME',
                'content': event.datetime_start.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p')
            },
            {
                'name': 'END_TIME',
                'content': event.datetime_end.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p')
            },
            {
                'name': 'LOCATION',
                'content': event.location
            },
            {
                'name': 'DESCRIPTION',
                'content': event.description
            },
            {
                'name': 'DATE',
                'content': event.datetime_start.astimezone(pytz.timezone(tz)).strftime('%b %d, %Y')
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
        email_confirmation = None

        if message:
            logger.debug(
                'message from user %s re: event %d',
                user.username,
                event.id
            )

            if is_coord:
                # contact all volunteers
                reg_receipients = [
                    {
                        'email': reg.user.email,
                        'name': reg.user.first_name,
                        'type': 'to'
                    }
                    for reg in UserEventRegistration.objects.filter(
                        event__id=event.id,
                        is_confirmed=True
                    )
                ]

                glogger_struct = {
                    'msg': 'event message from coordinator',
                    'username': user.email,
                    'eventid': event.id,
                    'volunteer_count': len(reg_receipients)
                }
                glogger.log_struct(glogger_struct, labels=glogger_labels)

                try:
                    merge_var_list.append({'name': 'MESSAGE', 'content': message})
                    sendBulkEmail(
                        'coordinator-messaged',
                        None,
                        merge_var_list,
                        reg_receipients,
                        user.email
                    )
                except Exception as e:
                    logger.error(
                        'unable to send email: %s (%s)',
                        e,
                        type(e)
                    )
                    return redirect('openCurrents:500')

            else:
                glogger_struct = {
                    'msg': 'event message from volunteer',
                    'username': user.email,
                    'eventid': event.id
                }

                email_template = 'volunteer-messaged'
                merge_var_list.append({'name': 'MESSAGE', 'content': message})

                if is_registered:
                    # message coordinator as a pre-registered volunteer
                    merge_var_list.append({'name': 'REGISTER', 'content': False})
                    glogger_struct['user_status'] = 'pre-registered'
                else:
                    # message coordinator as a new volunteer
                    email_confirmation = 'volunteer-confirmation'
                    merge_var_list.append({'name': 'REGISTER', 'content': True})
                    glogger_struct['user_status'] = 'new'

                glogger.log_struct(glogger_struct, labels=glogger_labels)

        # if no message was entered and a new UserEventRegistration was created
        elif not is_registered and not is_coord:
            email_template = 'volunteer-registered'
            email_confirmation = 'volunteer-confirmation'
            merge_var_list.append({'name': 'REGISTER', 'content': True})

        else:
            return redirect(
                'openCurrents:event-detail',
                pk=event.id,
                status_msg='Please enter a message',
                msg_type='alert'
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

        if email_confirmation:
            try:
                sendContactEmail(
                    email_confirmation,
                    None,
                    merge_var_list,
                    user.email,
                    event.coordinator.email
                )
            except Exception as e:
                logger.error(
                    'unable to send email: %s (%s)',
                    e.message,
                    type(e)
                )

        # TODO: add a redirect for coordinator who doesn't register
        return redirect('openCurrents:registration-confirmed', event.id)
    else:
        logger.error('Invalid form: %s', form.errors.as_data())
        return redirect('openCurrents:event-detail', event.id)


@login_required
def event_register_live(request, eventid):
    glogger_labels = {
        'handler': 'event_register_live'
    }
    userid = request.POST['userid']

    try:
        user = User.objects.get(id=userid)
    except User.ObjectDoesNotExist:
        logger.debug('user %s does not exist', userid)
        return HttpResponse(content=json.dumps({}), status=400)

    try:
        event = Event.objects.get(id=eventid)
    except Event.ObjectDoesNotExist:
        logger.debug('event %s does not exist', eventid)
        return HttpResponse(content=json.dumps({}), status=400)

    user_event, was_created = UserEventRegistration.objects.get_or_create(
        user=user, event=event
    )

    if not was_created:
        logger.debug(
            'user %s is already registered for event %s',
            user.username,
            event.id
        )
        return HttpResponse(content=json.dumps({}), status=200)

    logger.debug(
        'user %s registered for event %s', user.username, event.id
    )

    now = datetime.now(tz=pytz.utc)
    event_status = now > event.datetime_start - timedelta(minutes=15)
    event_status &= now < event.datetime_end + timedelta(minutes=15)

    glogger_struct = {
        'msg': 'user registered for event live',
        'username': user.email,
        'eventid': eventid,
        'event_in_progress': event_status
    }
    glogger.log_struct(glogger_struct, labels=glogger_labels)

    return HttpResponse(
        content=json.dumps({
            'userid': userid,
            'eventid': eventid,
            'event_status': int(event_status)
        }),
        status=201
    )


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
        status = 'success'
    except Exception as e:
        logger.error(
            'unable to send transactional email: %s (%s)',
            e.message,
            type(e)
        )
        status = 'fail'

    return redirect('openCurrents:check-email', user_email, status)


@login_required
def org_user_list(request, org_id):
    # return the list of admins for an org
    org_user = OcOrg(org_id).get_admins()
    org_user_list = dict([
        (orguser.id, {
            'firstname': orguser.first_name,
            'lastname': orguser.last_name
        })
        for orguser in org_user
        # include current userid, instead disable it in select GUI
        # if orguser.user.id != request.user.id
    ])

    return HttpResponse(
        content=json.dumps(org_user_list),
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
        status = 'success'
    except Exception as e:
        logger.error(
            'unable to send transactional email: %s (%s)',
            e.message,
            type(e)
        )
        status = 'fail'

    return redirect('openCurrents:check-email-password', user_email, status)


def process_signup(
    request,
    referrer=None,
    endpoint=False,
    verify_email=True,
    mock_emails=False
):
    glogger_labels = {
        'handler': 'process_signup'
    }
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
        isExisting = False
        try:
            if org_name and Org.objects.filter(name=org_name).exists():
                return redirect(
                    'openCurrents:login',
                    status_msg='Organization named %s already exists!' % org_name,
                    msg_type='alert'
                )
            else:
                user = OcUser().setup_user(
                    username=user_email,
                    email=user_email,
                    first_name=user_firstname,
                    last_name=user_lastname
                )

        except UserExistsException:
            logger.debug('user %s already exists', user_email)
            isExisting = True
            user = User.objects.get(username=user_email)

            update_name = False
            if user_firstname:
                user.first_name = user_firstname
                update_name = True

            if user_lastname:
                user.last_name = user_lastname
                update_name = True

            if update_name:
                user.save()

            if endpoint and not verify_email:
                return HttpResponse(user.id, status=200)

            elif user.has_usable_password() and not endpoint:
                logger.info('user %s already verified', user_email)
                return redirect(
                    'openCurrents:login',
                    status_msg='User with this email already exists',
                    msg_type='alert'
                )

        # user org
        if org_name:
            org = None
            try:
                org = OcOrg().setup_org(
                    name=org_name,
                    status=org_status
                )

                org_user = OrgUserInfo(user.id)
                org_user.setup_orguser(org=org, is_admin=org_status == 'biz')

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
                                'content': org_status
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

                if not isExisting and not mock_emails:
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
                # for testing purposes
                else:
                    request.session['invitation_email'] = 'True'

        # return
        if endpoint:
            return HttpResponse(user.id, status=201)
        else:
            if org_name:
                glogger_struct = {
                    'msg': 'new user invited by org',
                    'username': user_email,
                    'orgname': org_name
                }
                glogger.log_struct(glogger_struct, labels=glogger_labels)

                return redirect(
                    'openCurrents:check-email',
                    user_email,
                    org.id
                )
            else:
                glogger_struct = {
                    'msg': 'new user signup',
                    'username': user_email
                }
                glogger.log_struct(glogger_struct, labels=glogger_labels)

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

    def is_any_org_admin(user_to_check_id):
        try:
            is_admin_npf = OcAuth(user_to_check_id).is_admin_org()
            is_admin_biz = OcAuth(user_to_check_id).is_admin_biz()
        except:
            is_admin_npf = is_admin_biz = False
        return is_admin_npf or is_admin_biz

    if form.is_valid():
        org_name = form.cleaned_data['org_name']
        contact_name = form.cleaned_data['contact_name']
        contact_email = form.cleaned_data['contact_email']

        try:
            user_to_check = User.objects.get(email=contact_email)
        except:
            user_to_check = None

        if not user_to_check:
            is_admin = False
        else:
            try:
                user_to_check = User.objects.get(email=contact_email)
                is_admin = is_any_org_admin(user_to_check.id)
            except:
                is_admin = False

        try:
            org_exists = Org.objects.filter(name=org_name).exists()
        except:
            org_exists = False

        # send email to bizdev in any case
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

        if org_exists:
            return redirect(
                'openCurrents:profile',
                status_msg='It seems that {} is already active on openCurrents. Thanks for the nomination!.'.format(org_name),
                msg_type='alert'
            )

        else:
            # if it's a new user or existing user but not affiliated
            if not user_to_check or (user_to_check and not is_admin):
                # emailing admin with volunteer-invites-org
                sendTransactionalEmail(
                    'volunteer-nominates-org',
                    None,
                    [
                        {
                            'name': 'ADMIN_NAME',
                            'content': contact_name
                        },
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
                    contact_email
                )

                return redirect(
                    'openCurrents:profile',
                    status_msg='Thank you for nominating {} and growing our community! We will reach out soon.'.format(org_name),
                )

            # else user exists and affiliated
            else:
                return redirect(
                    'openCurrents:profile',
                    status_msg='It seems that {} is already affiliated with an organization on openCurrents. Thanks for the nomination!'.format(contact_email),
                    msg_type='alert'
                )

    return redirect(
        'openCurrents:time-tracker',
        status_msg='Organization name is required',
        msg_type='alert'
    )


def process_login(request):
    glogger_labels = {
        'handler': 'process_login'
    }
    form = UserLoginForm(request.POST)

    # valid form data received
    if form.is_valid():
        user_name = form.cleaned_data['user_email']
        user_password = form.cleaned_data['user_password']

        try:
            redirection = request.POST['next']
        except:
            redirection = None

        user = authenticate(
            username=user_name,
            password=user_password
        )

        if user is not None and user.is_active:
            glogger_struct = {
                'msg': 'login successful',
                'username': user.email
            }
            glogger.log_struct(glogger_struct, labels=glogger_labels)

            userid = user.id
            app_hr = 0
            today = date.today()

            # do a weekly check for unapproved requests (popup)
            if not user.last_login or user.last_login.date() < today - timedelta(days=today.weekday()):
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

            if redirection:
                return redirect(redirection)
            else:
                return redirect('openCurrents:profile', app_hr)

        else:
            glogger_struct = {
                'msg': 'login invalid',
                'username': user.email
            }
            glogger.log_struct(glogger_struct, labels=glogger_labels)

            return redirect(
                'openCurrents:login',
                status_msg='Invalid login/password.',
                msg_type='alert'
            )
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
        return redirect(
            'openCurrents:login',
            status_msg=errors[0],
            msg_type='alert'
        )


def process_email_confirmation(request, user_email):
    glogger_labels = {
        'handler': 'process_email_confirmation'
    }
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
            user_settings.monthly_updates = True

        user_settings.save()

        logger.debug('verification of user %s is complete', user.email)
        glogger_struct = {
            'msg': 'user verified',
            'username': user.email,
            'token': token
        }
        glogger.log_struct(glogger_struct, labels=glogger_labels)

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

    # if form was invalid for bad password, still need to preserve token
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
            status_msg=errors[0],
            msg_type='alert'
        )


def password_reset_request(request):
    glogger_labels = {
        'handler': 'password_reset_request'
    }
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
            logger.debug('verified user %s, send password reset email', user_email)
            glogger_struct = {
                'msg': 'password reset request',
                'username': user.email
            }
            glogger.log_struct(glogger_struct, labels=glogger_labels)

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
        status_msg = errors[0]
        return redirect('openCurrents:login')


def process_reset_password(request, user_email):
    glogger_labels = {
        'handler': 'process_reset_password'
    }
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
            logger.debug('verified user %s, allow password reset', user_email)
            glogger_struct = {
                'msg': 'password changed',
                'username': user.email,
                'token': token
            }
            glogger.log_struct(glogger_struct, labels=glogger_labels)

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
        status_msg = errors[0]
        return redirect('openCurrents:reset-password', user_email, token, status_msg)


@login_required
def process_org_signup(request):
    glogger_labels = {
        'handler': 'process_org_signup'
    }
    form = OrgSignupForm(request.POST)

    # valid form data received
    if form.is_valid():
        form_data = form.cleaned_data
        org = OcOrg().setup_org(
            name=form_data['org_name'],
            status=form_data['org_status']
        )

        org_user = OrgUserInfo(request.user.id)
        org_user.setup_orguser(org=org, is_admin=form_data['org_status'] == 'biz')

        logger.info(
            'Successfully created org %s nominated by %s',
            org.name,
            request.user.email
        )
        glogger_struct = {
            'msg': 'org signup',
            'username': request.user.email,
            'orgname': org.name
        }
        glogger.log_struct(glogger_struct, labels=glogger_labels)

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
    TODO: convert to an API call parametrized by user id
    '''
    balance = OcUser(request.user.id).get_balance_available()
    return HttpResponse(
        balance,
        status=200
    )


@login_required
def get_user_master_offer_remaining(request):
    '''
    GET remaining amount (in currents) that can be applied to the master offer redemption
    TODO: convert to an API call parametrized by user id
    '''
    balance = OcUser(request.user.id).get_master_offer_remaining()
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


def sendTransactionalEmail(template_name, template_content, merge_vars, recipient_email, **kwargs):

    # adding launch function marker to session for testing purpose
    test_time_tracker_mode = None
    if kwargs:
        sess = kwargs['session']
        marker = kwargs['marker']
        sess['transactional'] = kwargs['marker']
        test_time_tracker_mode = kwargs['test_time_tracker_mode']

    # mocking email function for testing purpose
    if not test_time_tracker_mode:
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
    else:
        logger.debug('test mode: mocking mandrill call')


def sendBulkEmail(template_name, template_content, merge_vars, recipient_email, sender_email, **kwargs):

    # adding launch function marker to session for testing purpose
    test_mode = None
    if kwargs:
        sess = kwargs['session']
        marker = kwargs['marker']
        sess['bulk'] = kwargs['marker']
        test_mode = kwargs['test_mode']

    # mocking email function for testing purpose
    if not test_mode:
        mandrill_client = mandrill.Mandrill(config.MANDRILL_API_KEY)
        message = {
            'from_email': 'info@opencurrents.com',
            'from_name': 'openCurrents',
            'to': recipient_email,
            'headers': {
                'Reply-To': sender_email.encode('ascii', 'ignore')
            },
            'global_merge_vars': merge_vars
        }

        mandrill_client.messages.send_template(
            template_name=template_name,
            template_content=template_content,
            message=message
        )

    else:
        logger.info('test mode: mocking mandrill call')
        sess['recepient'] = recipient_email
        sess['merge_vars'] = merge_vars
