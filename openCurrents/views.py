from django.shortcuts import render, redirect
from django.views.generic import View, TemplateView
from django.contrib.auth.models import User
from django.db import IntegrityError

from openCurrents import config
from openCurrents.models import Account, Token
from openCurrents.forms import UserSignupForm, EmailVerificationForm

from datetime import datetime, timedelta

import mandrill
import logging
import uuid


logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class HomeView(TemplateView):
    template_name = 'home.html'

class InviteView(TemplateView):
    template_name = 'home.html'

class ConfirmAccountView(TemplateView):
    template_name = 'confirm-account.html'

class CommunityView(TemplateView):
    template_name = 'community.html'

class LoginView(TemplateView):
    template_name = 'login.html'

class InviteFriendsView(TemplateView):
    template_name = 'invite-friends.html'

    def get_context_data(self, **kwargs):
        context = super(InviteFriendsView, self).get_context_data(**kwargs)
        try:
            account = Account.objects.get(user__username=context['referrer'])
            context['balance_pending'] = account.pending
        except:
            context['balance_pending'] = 0

        return context

class ApproveHoursView(TemplateView):
    template_name = 'approve-hours.html'

class CausesView(TemplateView):
    template_name = 'causes.html'

class EditHoursView(TemplateView):
    template_name = 'edit-hours.html'

class FaqView(TemplateView):
    template_name = 'faq.html'

class FindOrgsView(TemplateView):
    template_name = 'find-orgs.html'

class GiveCurrentsView(TemplateView):
    template_name = 'give-currents.html'

class HoursApprovedView(TemplateView):
    template_name = 'hours-approved.html'

class InventoryView(TemplateView):
    template_name = 'Inventory.html'

class MissionView(TemplateView):
    template_name = 'mission.html'

class NominateView(TemplateView):
    template_name = 'nominate.html'

class NominationConfirmedView(TemplateView):
    template_name = 'nomination-confirmed.html'

class NominationEmailView(TemplateView):
    template_name = 'nomination-email.html'

class OrgHomeView(TemplateView):
    template_name = 'org-home.html'

class OrgSignupView(TemplateView):
    template_name = 'org-signup.html'

class RequestCurrentsView(TemplateView):
    template_name = 'request-currents.html'

class SellView(TemplateView):
    template_name = 'sell.html'

class SignupView(TemplateView):
    template_name = 'signup.html'

class TellYourBossView(TemplateView):
    template_name = 'tell-your-boss.html'

class UserHomeView(TemplateView):
    template_name = 'user-home.html'

class VerifyIdentityView(TemplateView):
    template_name = 'verify-identity.html'

class VolunteerHoursView(TemplateView):
    template_name = 'volunteer-hours.html'

class VolunteerRequestsView(TemplateView):
    template_name = 'volunteer-requests.html'


def process_signup(request, referrer):
    form = UserSignupForm(request.POST)

    # valid form data received
    if form.is_valid():
        user_firstname = form.cleaned_data['user_firstname']
        user_lastname = form.cleaned_data['user_lastname']
        user_email = form.cleaned_data['user_email']
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
        return redirect('openCurrents:community')

    # fail with form validation error
    else:
        logger.error(
            'Invalid signup request: %s',
            form.errors.as_data()
        )

        # just report the first validation error
        errors = [
            '%s: %s' % (field, error)
            for field, le in form.errors.as_data().iteritems()
            for error in le
        ]
        return redirect('openCurrents:signup', status_msg=errors[0])


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
                status_msg= error_msg % user_email
            )

        if user.has_usable_password():
            logger.warning('user %s has already been verified', user_email)
            return redirect(
                'openCurrents:invite-friends',
                referrer=user.username
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
                status_msg = error_msg % user_email
            )

        if token_record.is_verified:
            logger.warning('token for %s has already been verified', user_email)
            return redirect(
                'openCurrents:invite-friends',
                referrer=user.username
            )

        # mark the verification record as verified
        token_record.is_verified = True
        token_record.save()

        # set user password (changed the user to one with password now)
        user_password = form.cleaned_data['user_password']
        user.set_password(user_password)
        user.save()

        # create user account
        user_account = Account(user=user)
        user_account.save()

        # add credit to the referrer
        if token_record.referrer:
            referrer_account = Account.objects.get(
                user=token_record.referrer
            )
            referrer_account.pending += 1
            referrer_account.save()

        logger.info('verification of user %s is complete', user_email)

        # send verification email
        try:
            sendTransactionalEmail(
                'invite-friends',
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

        return redirect(
            'openCurrents:invite-friends',
            referrer=user.username
        )

    else:
        logger.error(
            'Invalid confirm email request: %s',
            form.errors.as_data()
        )

        # just report the first validation error
        errors = [
            '%s: %s' % (field, error)
            for field, le in form.errors.as_data().iteritems()
            for error in le
        ]
        return redirect('openCurrents:home', status_msg=errors[0])


def sendTransactionalEmail(template_name, template_content, merge_vars, recipient_email):
    mandrill_client = mandrill.Mandrill(config.MANDRILL_API_KEY)
    message = {
        'from_email': 'info@opencurrents.com',
        'from_name': 'openCurrents',
        'to': [{
            'email': recipient_email,
            'type': 'to'
        }],
        'subject': 'Join openCurrents community',
        'global_merge_vars': merge_vars
    }

    mandrill_client.messages.send_template(
        template_name=template_name,
        template_content=template_content,
        message=message
    )
