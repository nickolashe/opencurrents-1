from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.forms import ModelForm

from openCurrents.models import Project, Org, OrgUser, User

from datetime import datetime

import logging
import re
import pytz
import string


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


class PasswordResetRequestForm(forms.Form):
    user_email = forms.CharField(min_length=1)

class UserLoginForm(forms.Form):
    user_email = forms.CharField(min_length=1)
    user_password = forms.CharField(min_length=1)


def validate_password_strength(new_password, new_password_confirm):
        """Validates that a password is as least 8 characters long and has at least
        1 digit, 1 letter, an uppercase characte and a special character.
        """
        min_length = 8

        if new_password and new_password_confirm and new_password != new_password_confirm:
            raise ValidationError(_('Passwords don\'t match. Please check again.'))

        #check for minimum length
        if len(new_password) < min_length:
            raise ValidationError(_('Please make sure that the password has at least {0} characters '
                                    'long.').format(min_length))

        # check for digit
        if not any(char.isdigit() for char in new_password):
            raise ValidationError(_('Please make sure that the password contains at least 1 digit.'))

        # check for letter
        if not any(char.isalpha() for char in new_password):
            raise ValidationError(_('Please make sure that the password contains at least 1 letter.'))

        #check for special character
        specialChars = set(string.punctuation.replace("_", ""))
        if not any(char in specialChars for char in new_password):
            raise ValidationError(_('Please make sure that the password contains at least 1 special character.'))

        #check for atleast 1 uppercase chanracter
        if not any(char.isupper() for char in new_password):
            raise ValidationError(_('Please make sure that the password contains at least 1 uppercase character.'))

class EmailVerificationForm(forms.Form):
    user_password = forms.CharField(min_length=8)
    user_password_confirm = forms.CharField(min_length=8)
    verification_token = forms.UUIDField()
    monthly_updates = forms.BooleanField(initial=False,required=False)

    def clean(self):
        cleaned_data = super(EmailVerificationForm, self).clean()

        # check if passwords match
        user_password = cleaned_data.get('user_password')
        user_password_confirm = cleaned_data.get('user_password_confirm')
        validate_password_strength(str(user_password), str(user_password_confirm))
        # if user_password and user_password_confirm and user_password != user_password_confirm:
        #     raise ValidationError(_('Passwords don\'t match'))
        # if re.match(r'((?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%]).{8,})', user_password):
        #     # match
        #     pass
        # else:
        #     raise ValidationError(_('Password does\'nt meet the required criterion.'))


class PasswordResetForm(forms.Form):
    new_password = forms.CharField(min_length=8)
    new_password_confirm = forms.CharField(min_length=8)
    verification_token = forms.UUIDField()

    def clean(self):
        cleaned_data = super(PasswordResetForm, self).clean()

        # check if passwords match
        new_password = cleaned_data.get('new_password')
        new_password_confirm = cleaned_data.get('new_password_confirm')
        validate_password_strength(str(new_password), str(new_password_confirm))
        # if new_password and new_password_confirm and new_password != new_password_confirm:
        #     raise ValidationError(_('Passwords don\'t match'))
        # if re.match(r'((?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[@#$%]).{8,})', user_password):
        #     # match
        #     pass
        # else:
        #     raise ValidationError(_('Password does\'nt meet the required criterion.'))

class OrgNominationForm(forms.Form):
    org_name = forms.CharField(min_length=1,required=True)
    contact_name = forms.CharField(min_length=1,required=True)
    contact_email = forms.CharField(min_length=1,required=True)

    def clean(self):
        cleaned_data = super(OrgNominationForm, self).clean()
        org_name = cleaned_data['org_name']
        contact_name = cleaned_data['contact_name']
        contact_email = cleaned_data['contact_email']


class OrgSignupForm(forms.Form):
    org_name = forms.CharField(min_length=1)
    org_website = forms.CharField(min_length=1,required=False)
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

    CHOICES = [(True, 'event-privacy-1'), (False, 'event-privacy-2')]
    
    is_public = forms.ChoiceField(widget=forms.RadioSelect(
        attrs={"class": "hidden styled-radio"}), 
        choices=CHOICES, 
        initial='True'
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
        widget=forms.TextInput(attrs={'placeholder': 'First name','value':''})
    )
    coordinator_email = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Email','value':''})
    )

    def clean(self):
        cleaned_data = super(ProjectCreateForm, self).clean()
        date_start = cleaned_data['date_start']
        time_start = cleaned_data['time_start']
        time_end = cleaned_data['time_end']
        tz = self.org.timezone

        try:
            datetime_start = datetime.strptime(
                ' '.join([date_start, time_start]),
                '%Y-%m-%d %I:%M%p'
            )
        except:
            raise ValidationError(_('Bad date/start time format entered.'))
     

        try:
            datetime_end = datetime.strptime(
                ' '.join([date_start, time_end]),
                '%Y-%m-%d %I:%M%p'
            )
        except:
            raise ValidationError(_('Bad end time format entered.'))

        cleaned_data['datetime_start'] = pytz.timezone(tz).localize(datetime_start)
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

    choices_init = [("select_org","Select organization")]
    choices = [
        (org.id, org.name)
        for org in Org.objects.all().order_by('name')
    ]
    choices = choices_init + choices
    org = forms.ChoiceField(
        choices=choices,
        widget=forms.Select(attrs={
            'id': 'id_org_choice'
        })
    )
    
    #choices_init_admin = [("select_admin","Select admin")]
    # choices_admin = [
    #     (user.id, user.username)
    #     for user in User.objects.all().filter().order_by('username')
    # ]
    choices_admin = [("select_admin","Select admin")]
    #choices_admin = choices_init_admin + choices_admin
    admin = forms.CharField(
        #choices=choices_admin,
        required=False,
        widget=forms.Select(attrs={
            'id': 'id_admin_choice'
        })
    )

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
            'id': 'volunteer-date',
            'name':'volunteer-date',
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
        try:
            self.org = Org.objects.get(id=cleaned_data['org'])
            #admin = cleaned_data['admin']
            tz = self.org.timezone
        except KeyError:
            raise ValidationError(_('Select the Org you worked for'))

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
        if datetime_end == datetime_start:
            raise ValidationError(_('Please select a valid time'))
            

        return cleaned_data


class EventCheckinForm(forms.Form):
    userid = forms.IntegerField()
    checkin = VolunteerCheckinField()
