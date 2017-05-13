from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render, redirect
from django.views.generic import View, TemplateView
from django.contrib.auth.models import User
from django.db import IntegrityError

from openCurrents import config
from openCurrents.models import \
    Account, \
    Org, \
    OrgUser, \
    Token

from openCurrents.forms import \
    UserSignupForm, \
    UserLoginForm, \
    EmailVerificationForm, \
    OrgSignupForm

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

    # def get_context_data(self, **kwargs):
    #     context = super(ConfirmAccountView, self).get_context_data(**kwargs)
    #     org_name = None
    #     try:
    #         org_user = OrgUser.objects.get(user__email=context['email'])
    #         if org_user:
    #             org_name = org_user.org.name
    #             context['org_name'] = org_name
    #     except:
    #         logger.info('User %s has no org association', context['email'])
    #
    #     return context

class CommunityView(TemplateView):
    template_name = 'community.html'

class LoginView(TemplateView):
    template_name = 'login.html'

class InviteFriendsView(LoginRequiredMixin, TemplateView):
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

class OrgSignupView(LoginRequiredMixin, TemplateView):
    template_name = 'org-signup.html'

class RequestCurrentsView(TemplateView):
    template_name = 'request-currents.html'

class SellView(TemplateView):
    template_name = 'sell.html'

class SignupView(TemplateView):
    template_name = 'signup.html'

class OrgApprovalView(TemplateView):
    template_name = 'org-approval.html'

class UserHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'user-home.html'

class VerifyIdentityView(TemplateView):
    template_name = 'verify-identity.html'

class VolunteerHoursView(TemplateView):
    template_name = 'volunteer-hours.html'

class VolunteeringView(TemplateView):
    template_name = 'volunteering.html'

class VolunteerRequestsView(TemplateView):
    template_name = 'volunteer-requests.html'

class ProfileView(TemplateView):
    template_name = 'profile.html'

class EditProfileView(TemplateView):
    template_name = 'edit-profile.html'

class BlogView(TemplateView):
    template_name = 'Blog.html'

class CreateProjectView(TemplateView):
    template_name = 'create-project.html'

class ProjectDetailsView(TemplateView):
    template_name = 'project-details.html'

class InviteVolunteersView(TemplateView):
    template_name = 'invite-volunteers.html'

class ProjectCreatedView(TemplateView):
    template_name = 'project-created.html'


def process_signup(request, referrer):
    form = UserSignupForm(request.POST)

    # valid form data received
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
            if user.has_usable_password():
                logger.info('user %s already verified', user_email)
                return redirect(
                    'openCurrents:signup',
                    status_msg='User with this email already exists'
                )
            else:
                logger.info('user %s has not been verified', user_email)

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
        return redirect(
            'openCurrents:confirm-account',
            email=user_email
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
            login(request, user)
            return redirect('openCurrents:user-home')
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
                status_msg= error_msg % user_email
            )

        if user.has_usable_password():
            logger.warning('user %s has already been verified', user_email)
            return redirect('openCurrents:user-home')

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
            return redirect('openCurrents:user-home')

        # mark the verification record as verified
        token_record.is_verified = True
        token_record.save()

        # set user password (changed the user to one with password now)
        user_password = form.cleaned_data['user_password']
        user.set_password(user_password)
        user.save()

        # create user account
        user_account = Account(user=user, pending=1)
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

        login(request, user)

        try:
            org_user = OrgUser.objects.get(user=user)
            org_name = org_user.org.name
            return redirect('openCurrents:org-signup', org_name=org_name)

        except:
            logger.info('No org association')
            return redirect('openCurrents:user-home')

    else:
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
            status_msg=errors[0]
        )


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

        org = Org.objects.get(website=form_data['org_website'])
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
            org_user.affiliation=form_data['user_affiliation']
            org_user.save()

        logger.info(
            'Successfully created / updated org %s nominated by %s',
            org.name,
            request.user.email
        )
        return redirect(
            'openCurrents:user-home',
            status_msg='Thank you for nominating %s to openCurrents!' % org.name
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
