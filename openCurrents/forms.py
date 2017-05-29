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
    def __init__(self, *args, **kwargs):
        orgid = kwargs.pop('orgid')
        super(ProjectCreateForm, self).__init__(*args, **kwargs)

        # project_id field
        self.fields['project_id'] = forms.ChoiceField(
            label='Let\'s',
            choices=[
                (project.id, project.name)
                for project in Project.objects.filter(org__id=orgid)
            ]
        )

    description = forms.CharField(
        label='Project description',
        help_text='What should volunteers know? What should they bring?'
    )
    date_start = forms.CharField(
        label='on',
        widget=forms.TextInput(attrs={
            'id': 'date_start',
            'class': 'center'
        })
    )
    time_start = forms.CharField(
        label='from',
        widget=forms.TextInput(attrs={
            'id': 'time_start',
            'class': 'center',
            'placeholder': '9:00 am'
        })
    )
    time_end = forms.CharField(
        label='to',
        widget=forms.TextInput(attrs={
            'id': 'time_end',
            'class': 'center',
            'placeholder': '12:00 pm'
        })
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

    def clean(self):
        cleaned_data = super(ProjectCreateForm, self).clean()
        date_start = cleaned_data['date_start']
        time_start = cleaned_data['time_start']
        time_end = cleaned_data['time_end']

        cleaned_data['datetime_start'] = datetime.strptime(
            ' '.join([date_start, time_start]),
            '%Y-%m-%d %I:%M%p'
        )
        cleaned_data['datetime_end'] = datetime.strptime(
            ' '.join([date_start, time_end]),
            '%Y-%m-%d %I:%M%p'
        )

        return cleaned_data

# TODO: Add location to form
class EventRegisterForm(forms.Form):
    contact_message = forms.CharField(
        label='Contact project coordinator (optional)',
        help_text='Ask a question, confirm your attendance, or just say hello',
        widget=forms.Textarea(attrs={
            'rows': '4'
        })
    )
