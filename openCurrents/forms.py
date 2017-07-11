from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.forms import ModelForm

from openCurrents.models import Project, Org, OrgUser

from datetime import datetime

import logging
import pytz


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class NotValidatedMultipleChoiceField(forms.TypedMultipleChoiceField):
    """Field that do not validate if the field values are in self.choices"""

    def to_python(self, value):
        """Override checking method"""
        return map(self.coerce, value)

    def validate(self, value):
        """Nothing to do here"""
        pass


# class VolunteerIdField(forms.Field):
#     def __init__(self, *args, **kwargs):
#         super(VolunteerIdField, self).__init__(self, *args, **kwargs)
#
#     def to_python(self, value):
#         logger.info(value)
#         if isinstance(value, list) and len(value) == 1:
#             return value[0]
#         else:
#             raise ValidationError(_('Invalid id input'))


class VolunteerCheckinField(forms.Field):

    def __init__(self, *args, **kwargs):
        super(VolunteerCheckinField, self).__init__(self, *args, **kwargs)

    def to_python(self, value):
        if value == 'true':
            return True
        elif value == 'false':
            return False
        else:
            raise ValidationError(_('Invalid checkin input'))


#class UserResendForm(forms.Form):
#     user_email = forms.EmailField(
#        widget=forms.EmailInput(attrs={
#            'id': 'email',
#            'placeholder': 'Email'
#        })
#    )

class UserSignupForm(forms.Form):
    user_firstname = forms.CharField(
        widget=forms.TextInput(attrs={
            'id': 'new-firstname',
            'placeholder': 'Firstname'
        })
    )
    user_lastname = forms.CharField(
        widget=forms.TextInput(attrs={
            'id': 'new-lastname',
            'placeholder': 'Lastname'
        })
    )
    user_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'id': 'new-email',
            'placeholder': 'Email'
        })
    )
    org_name = forms.CharField(required=False, min_length=2)


class UserLoginForm(forms.Form):
    user_email = forms.CharField(min_length=1)
    user_password = forms.CharField(min_length=1)


class EmailVerificationForm(forms.Form):
    user_password = forms.CharField(min_length=8)
    user_password_confirm = forms.CharField(min_length=8)
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
        choices=[
            ('employee', 'employee'),
            ('leader', 'leader'),
            ('volunteer', 'volunteer'),
            ('unaffiliated', 'unaffiliated')
        ]
    )
    org_status = forms.ChoiceField(
        choices=[
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
        self.org = Org.objects.get(id=orgid)
        super(ProjectCreateForm, self).__init__(*args, **kwargs)

    # project_id field
    # self.fields['project_id'] = forms.ChoiceField(
    #     label='Let\'s',
    #     choices=[
    #         (project.id, project.name)
    #         for project in Project.objects.filter(org__id=orgid)
    #     ]
    # )

    project_name = forms.CharField(
        label='Let\'s...',
        widget=forms.TextInput(attrs={
            'class': ' center',
            'placeholder': 'do some good'
        })
    )
    description = forms.CharField(
        label='Project description',
        help_text='What should volunteers know? What should they bring?',
        widget=forms.Textarea(attrs={
            'rows': '3'
        })
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
    # location = forms.CharField(
    # location = NotValidatedMultipleChoiceField(
    #     label='at',
    #     widget=forms.TextInput(attrs={
    #         'class': 'location center',
    #         'id': 'event-location-1',
    #         'placeholder': 'location'
    #     })
    # )

    coordinator_firstname = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'First name'})
    )
    coordinator_email = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Email'})
    )

    def clean(self):
        cleaned_data = super(ProjectCreateForm, self).clean()
        date_start = cleaned_data['date_start']
        time_start = cleaned_data['time_start']
        time_end = cleaned_data['time_end']
        tz = self.org.timezone

        datetime_start = datetime.strptime(
            ' '.join([date_start, time_start]),
            '%Y-%m-%d %I:%M%p'
        )
        cleaned_data['datetime_start'] = pytz.timezone(tz).localize(datetime_start)

        datetime_end = datetime.strptime(
            ' '.join([date_start, time_end]),
            '%Y-%m-%d %I:%M%p'
        )
        cleaned_data['datetime_end'] = pytz.timezone(tz).localize(datetime_end)

        if cleaned_data['datetime_start'] > cleaned_data['datetime_end']:
            raise ValidationError(_('Start time needs to occur before End time'))

        return cleaned_data


# TODO: Add location to form
class EventRegisterForm(forms.Form):
    contact_message = forms.CharField(
        required=False,
        label='Contact project coordinator (optional)',
        help_text='Ask a question, confirm your attendance, or just say hello',
        widget=forms.Textarea(attrs={
            'rows': '4'
        }),
        max_length=16384
    )


class TrackVolunteerHours(forms.Form):

    choices_init = [("select org","select organisation")]
    choices = [
        (org.name, org.name)
        for org in Org.objects.all().order_by('name')
    ]
    choices = choices_init+choices
    orgs = forms.ChoiceField(choices=choices)

    description = forms.CharField(
        widget=forms.TextInput(attrs={
            #'rows': '1',
            'class': 'center large-text',
            'placeholder': 'Description of work'
        })
    )
    date_start = forms.CharField(
        #label='on',
        label = 'Date',
        widget=forms.TextInput(attrs={
            'id': 'start-date',
            'placeholder': 'yyyy-mm-dd'
        })
    )
    time_start = forms.CharField(
        #label='from',
        label = 'Start time',
        widget=forms.TextInput(attrs={
            'id': 'start-time',
            'name':'',
            'value': '12:00:00'
        })
    )
    time_end = forms.CharField(
        #label='to',
        label = 'End time',
        widget=forms.TextInput(attrs={
            'id': 'end-time',
            'name':'',
            'value': '12:00:00'
        })
    )

    def clean(self):
        cleaned_data = super(TrackVolunteerHours, self).clean()
        date_start = cleaned_data['date_start']
        time_start = cleaned_data['time_start']
        time_end = cleaned_data['time_end']
        tz = "America/Chicago"#self.org.timezone

        datetime_start = datetime.strptime(
            ' '.join([date_start, time_start]),
            '%Y-%m-%d %I:%M%p'
        )
        cleaned_data['datetime_start'] = pytz.timezone(tz).localize(datetime_start)

        datetime_end = datetime.strptime(
            ' '.join([date_start, time_end]),
            '%Y-%m-%d %I:%M%p'
        )
        cleaned_data['datetime_end'] = pytz.timezone(tz).localize(datetime_end)

        if cleaned_data['datetime_start'] > cleaned_data['datetime_end']:
            raise ValidationError(_('Start time needs to occur before End time'))

        return cleaned_data


class EventCheckinForm(forms.Form):
    userid = forms.IntegerField()
    checkin = VolunteerCheckinField()
