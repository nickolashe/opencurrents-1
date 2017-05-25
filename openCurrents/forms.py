from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.forms import ModelForm

from openCurrents.models import Project, OrgUser

from datetime import datetime

import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class UserSignupForm(forms.Form):
    user_firstname = forms.CharField()
    user_lastname = forms.CharField()
    user_email = forms.EmailField()
    org_name = forms.CharField(required=False, min_length=2)


class UserLoginForm(forms.Form):
    user_email = forms.CharField(min_length=1)
    user_password = forms.CharField(min_length=1)


class EmailVerificationForm(forms.Form):
    user_password = forms.CharField(min_length=10)
    user_password_confirm = forms.CharField(min_length=10)
    verification_token = forms.UUIDField()

    def clean(self):
        cleaned_data = super(EmailVerificationForm, self).clean()

        # check if passwords match
        user_password = cleaned_data.get('user_password')
        user_password_confirm = cleaned_data.get('user_password_confirm')
        if user_password and user_password_confirm and user_password != user_password_confirm:
            raise ValidationError(_('Passwords don\'t match'))


class OrgSignupForm(forms.Form):
    org_name = forms.CharField(min_length=1)
    org_website = forms.CharField(min_length=1)
    user_affiliation = forms.ChoiceField(
        choices = [
            ('employee', 'employee'),
            ('leader', 'leader'),
            ('volunteer', 'volunteer'),
            ('unaffiliated', 'unaffiliated')
        ]
    )
    org_status = forms.ChoiceField(
        choices = [
            ('nonprofit', 'nonprofit'),
            ('business', 'business'),
            ('unregistered', 'unregistered')
        ]
    )
    org_mission = forms.CharField(required=False)
    org_reason = forms.CharField(required=False)

    def clean_user_affiliation(self):
        return str(self.cleaned_data['user_affiliation'])

    def clean_org_status(self):
        return str(self.cleaned_data['org_status'])


class ProjectCreateForm(forms.Form):
    name = forms.CharField(
        label='Let\'s...'
    )
    description = forms.CharField(
        label='Project description'
    )
    date_start = forms.CharField(
        label='on'
    )
    time_start = forms.CharField(
        label='from'
    )
    time_end = forms.CharField(
        label='to'
    )
    location = forms.CharField(
        label='at',
        widget=forms.TextInput(attrs={'id': 'project-location'})
    )
    coordinator_firstname = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Coordinator Firstname'})
    )
    coordinator_email = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Coordinator Email'})
    )
    orgid = forms.CharField()

    def clean(self):
        cleaned_data = super(ProjectCreateForm, self).clean()
        logger.info(cleaned_data)
        date_start = cleaned_data['date_start']
        time_start = cleaned_data['time_start']
        time_end = cleaned_data['time_end']
        #userid = cleaned_data['userid']
        #orgid = OrgUser.objects.get(user__id=userid).org.id
        logger.info('orgid: %s', cleaned_data['orgid'])
        #cleaned_data['orgid'] = orgid

        cleaned_data['datetime_start'] = datetime.strptime(
            ' '.join([date_start, time_start]),
            '%Y-%m-%d %I:%M%p'
        )
        cleaned_data['datetime_end'] = datetime.strptime(
            ' '.join([date_start, time_start]),
            '%Y-%m-%d %I:%M%p'
        )

        logger.info('cleaned data: %s', cleaned_data)
        return cleaned_data
