from django import forms

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from django.template.defaultfilters import filesizeformat
from django.utils.translation import ugettext as _

from openCurrents.models import (
    Org,
    OrgUser,
    Offer,
    Project,
    Event
)

from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.ledger import OcLedger

from datetime import datetime, timedelta

import logging
import re
import pytz
import string
import widgets


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

class UserEmailForm(forms.Form):
    user_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'id': 'new-email',
            'placeholder': 'Email address',
            'class': 'lead center'
        })
    )

    def clean_user_email(self):
        return self.cleaned_data['user_email'].lower()


class UserSignupForm(UserEmailForm):
    user_firstname = forms.CharField(
        widget=forms.TextInput(attrs={
            'id': 'new-firstname',
            'placeholder': 'First name',
            'class': 'center'
        })
    )

    user_lastname = forms.CharField(
        widget=forms.TextInput(attrs={
            'id': 'new-lastname',
            'placeholder': 'Last name',
            'class': 'center'
        })
    )

    # org_name = forms.CharField(required=False, min_length=2)
    npf_name = forms.CharField(required=False, min_length=2)
    biz_name = forms.CharField(required=False, min_length=2)

    # org_status = forms.ChoiceField(
    #     choices=[
    #         ('npf', 'nonprofit'),
    #         ('biz', 'business'),
    #     ],
    #     required=False
    # )

    org_admin_id = forms.IntegerField(required=False)

    signup_status = forms.CharField(required=True, max_length=3)


class PasswordResetRequestForm(UserEmailForm):
    pass


class UserLoginForm(UserEmailForm):
    user_password = forms.CharField(min_length=1)


def validate_password_strength(new_password, new_password_confirm):
        """Validates that a password is as least 8 characters long and has at least
        1 digit, 1 letter, an uppercase characte and a special character.
        """
        min_length = 8

        if new_password and new_password_confirm and new_password != new_password_confirm:
            raise ValidationError(_('Passwords don\'t match. Please check again.'))

        # #check for minimum length
        if len(new_password) < min_length:
            raise ValidationError(_('Please make sure that the password has at least {0} characters '
                                    'long.').format(min_length))

        # # check for digit
        # if not any(char.isdigit() for char in new_password):
        #     raise ValidationError(_('Please make sure that the password contains at least 1 digit.'))

        # # check for letter
        # if not any(char.isalpha() for char in new_password):
        #     raise ValidationError(_('Please make sure that the password contains at least 1 letter.'))

        # #check for special character
        # specialChars = set(string.punctuation.replace("_", ""))
        # if not any(char in specialChars for char in new_password):
        #     raise ValidationError(_('Please make sure that the password contains at least 1 special character.'))

        # #check for atleast 1 uppercase chanracter
        # if not any(char.isupper() for char in new_password):
        #     raise ValidationError(_('Please make sure that the password contains at least 1 uppercase character.'))

class EmailVerificationForm(forms.Form):
    user_password = forms.CharField(min_length=8)
    user_password_confirm = forms.CharField(min_length=8)
    verification_token = forms.UUIDField()
    monthly_updates = forms.BooleanField(initial=False, required=False)

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
    contact_name = forms.CharField(min_length=1,required=False)
    contact_email = forms.CharField(min_length=1,required=False)

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
            ('npf', 'nonprofit'),
            ('biz', 'business'),
        ]
    )
    org_mission = forms.CharField(required=False)
    org_reason = forms.CharField(required=False)


class CreateEventForm(forms.Form):
    def __init__(self, *args, **kwargs):
        '''
        form init method:
            - fetches the org from db
            - kwargs contains orgid and is passed from the CreateEventView
            - builds coordinator choices list dynamically
            - sets admin user as the initial choice
        '''
        orgid = kwargs.pop('org_id')
        self.userid = kwargs.pop('user_id')
        self.org = Org.objects.get(id=orgid)

        # this needs to be called first to get access to self.fields
        super(CreateEventForm, self).__init__(*args, **kwargs)

        # build the coordinator choices list dynamically
        # set (preselect) initially to admin user
        coordinator_choices = self._get_coordinator_choices()
        self.fields['event_coordinator'].choices += coordinator_choices
        self.fields['event_coordinator'].initial = self.userid


    # form field definitions follow
    project_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': ' center',
            'placeholder': 'Event name'
        })
    )

    event_date = forms.CharField(
        label='on',
        widget=widgets.TextWidget(attrs={
            'id': 'event-date',
            'class': ' center',
            'placeholder': 'yyyy-mm-dd',
            'onfocus': 'blur();'
        })
    )

    event_starttime = forms.CharField(
        label='from',
        widget=widgets.TextWidget(attrs={
            'id': 'event-starttime',
            'class': ' center',
            'placeholder': '12:00 pm',
            'onfocus': 'blur();'
        })
    )

    event_endtime = forms.CharField(
        label='to',
        widget=widgets.TextWidget(attrs={
            'id': 'event-endtime',
            'class': ' center',
            'placeholder': '1:00 pm',
            'onfocus': 'blur();'
        })
    )

    event_privacy = forms.ChoiceField(
        widget=widgets.RadioWidget(
            attrs={
                'class': 'custom-radio',
            }
        ),
        choices=[(1, 'public'), (0, 'private')],
        initial=1
    )

    event_description = forms.CharField(
        label='Description',
        help_text='What should volunteers know? What should they bring?',
        widget=forms.Textarea(attrs={
            'rows': '3'
        }),
    )

    event_coordinator = forms.ChoiceField(
        choices=[('select_coord', 'Select coordinator')],
    )

    def _get_coordinator_choices(self):
        '''
        return list of org's approved admins (as coordinator choices)
            - admin group for any org is named 'admin_$n', where n = org_id
        '''
        orgs_admin_group = Group.objects.get(
            name='admin_%s' % self.org.id
        )

        choices_orgs_approved_admins = [
            (user.id, ' '.join([user.first_name, user.last_name]))
            for user in orgs_admin_group.user_set.all(
            ).order_by(
                'last_name'
            )
        ]

        return choices_orgs_approved_admins

    def clean(self):
        cleaned_data = super(CreateEventForm, self).clean()
        date_start = cleaned_data['event_date']
        time_start = cleaned_data['event_starttime']
        time_end = cleaned_data['event_endtime']
        tz = self.org.timezone

        try:
            datetime_start = datetime.strptime(
                ' '.join([date_start, time_start]),
                '%Y-%m-%d %I:%M%p'
            )
        except Exception as e:
            error_msg = 'Invalid event start time'
            logger.debug('%s: %s', error_msg, e.message)
            raise ValidationError(_(error_msg))

        try:
            datetime_end = datetime.strptime(
                ' '.join([date_start, time_end]),
                '%Y-%m-%d %I:%M%p'
            )
        except Exception as e:
            error_msg = 'Invalid event end time'
            logger.debug('%s: %s', error_msg, e.message)
            raise ValidationError(_(error_msg))

        cleaned_data['datetime_start'] = pytz.timezone(tz).localize(datetime_start)
        cleaned_data['datetime_end'] = pytz.timezone(tz).localize(datetime_end)

        if cleaned_data['datetime_start'] >= cleaned_data['datetime_end']:
            raise ValidationError(_('Start time needs to occur before End time'))

        return cleaned_data


class EditEventForm(CreateEventForm):
    def __init__(self, *args, **kwargs):
        event_id = kwargs.pop('event_id')
        user_id = kwargs.pop('user_id')
        self.event = Event.objects.get(id=event_id)
        self.org = self.event.project.org
        tz = self.org.timezone

        # call parent init in order to be able to access form fields
        #   - in this case parent (CreateEventForm) init requires the presence
        #     of org and user ids, so we provide those
        kwargs['org_id'] = self.org.id
        kwargs['user_id'] = user_id
        super(EditEventForm, self).__init__(*args, **kwargs)

        # populate event initial values
        self.fields['project_name'].initial = self.event.project.name
        self.fields['event_date'].initial = self.event.datetime_start.astimezone(
            pytz.timezone(tz)
        ).date()
        self.fields['event_starttime'].initial = self.event.datetime_start.astimezone(
            pytz.timezone(tz)
        ).time()
        self.fields['event_endtime'].initial = self.event.datetime_end.astimezone(
            pytz.timezone(tz)
        ).time()
        self.fields['event_privacy'].initial = int(self.event.is_public)
        self.fields['event_location'].initial = self.event.location

        # cleaning field from HREF tags
        text = unicode(self.event.description)

        patt1 = r'<a href=[^>]*>'
        patt2 = r'</a>'
        text = re.sub(patt1, "", text)
        text = re.sub(patt2, "", text)
        self.fields['event_description'].initial = text

        # self.fields['event_description'].initial = self.event.description

        # build the coordinator choices list dynamically
        # set (preselect) initially to existing coordinator
        #   - we are calling the parent (CreateEventForm) form's init,
        #     which already populates event_coordinator select
        #   - initial value is different from parents, however,
        #     we set to current event's coordinator
        self.fields['event_coordinator'].initial = self.event.coordinator.id

    # form fields are inherited from CreateEventForm
    # define extra fields only
    event_location = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'center',
            'id': 'event-location'
        }),
    )

    # def clean(self):
    #    '''
    #    inherited from CreateEventForm
    #    '''


# TODO: Add location to form
class EventRegisterForm(forms.Form):
    contact_message = forms.CharField(
        required=False,
        label='Get in touch (optional)',
        widget=forms.Textarea(attrs={
            'rows': '3'
        }),
        max_length=16384
    )


class TimeTrackerForm(forms.Form):

    # important to have the list generated dynamically in the init
    # to force update on each page refresh
    def __init__(self, *args, **kwargs):
        super(TimeTrackerForm, self).__init__(*args, **kwargs)

        # obtain the list of orgs with at least one approved admin
        orgs_approved_admins = Group.objects.filter(
            user__isnull=False
        ).filter(
            name__startswith='admin_'
        ).distinct()

        org_ids = [
            int(org_admin_group.name.split('_')[1])
            for org_admin_group in orgs_approved_admins
        ]

        orgs = Org.objects.filter(
            id__in=org_ids
        ).filter(
            status='npf'
        ).order_by(
            'name'
        )

        choices_orgs_approved_admins = [
            (org.id, org.name)
            for org in orgs
        ]

        # build the dynamic choices list
        self.fields['org'].choices += choices_orgs_approved_admins


    org = forms.ChoiceField(
        required=False,
        choices=[("select_org", "Select organization")],
        widget=forms.Select(attrs={
            'id': 'id_org_choice'
        })
    )

    choices_admin = [("select_admin","Select coordinator")]
    admin = forms.CharField(
        #choices=choices_admin,
        required=False,
        widget=forms.Select(attrs={
            'id': 'id_admin_choice',
            'disabled': True
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
            'placeholder': 'yyyy-mm-dd',
            'onfocus': 'blur();'
        })
    )
    time_start = forms.CharField(
        #label='from',
        label = 'Start time',
        widget=forms.TextInput(attrs={
            'id': 'start-time',
            'name':'',
            'value': '12:00:00',
            'onfocus': 'blur();'
        })
    )
    time_end = forms.CharField(
        #label='to',
        label = 'End time',
        widget=forms.TextInput(attrs={
            'id': 'end-time',
            'name':'',
            'value': '13:00:00',
            'onfocus': 'blur();'
        })
    )
    new_org = forms.CharField(
        required=False,
        widget=widgets.TextWidget(attrs={
            'class': 'center',
            'placeholder': 'Organization name',
        })
    )
    new_admin_name = forms.CharField(
        required=False,
        widget=widgets.TextWidget(attrs={
            'class': 'center',
            'placeholder': 'Coordinator name',
        })
    )
    new_admin_email = forms.EmailField(
        required=False,
        widget=widgets.TextWidget(attrs={
            'class': 'center',
            'placeholder': 'Coordinator email'
        })
    )

    def clean_new_admin_email(self):
        new_admin_email = self.cleaned_data.get('new_admin_email', '')
        return new_admin_email.lower()

    def clean(self):
        cleaned_data = super(TimeTrackerForm, self).clean()
        date_start = cleaned_data['date_start']
        time_start = cleaned_data['time_start']
        time_end = cleaned_data['time_end']

        # assert org
        if cleaned_data['org']:
            try:
                self.org = Org.objects.get(id=cleaned_data['org'])
                tz = self.org.timezone
            except KeyError:
                raise ValidationError(_('Select the organization you volunteered for'))
        else:
            tz = 'America/Chicago'

        # parse start time
        datetime_start = None
        try:
            datetime_start = datetime.strptime(
                ' '.join([date_start, time_start]),
                '%Y-%m-%d %I:%M%p'
            )
        except Exception as e:
            raise ValidationError(_('Invalid start time'))

        # localize start time to org's timezone
        cleaned_data['datetime_start'] = pytz.timezone(tz).localize(datetime_start)

        # parse end time
        datetime_end = None
        try:
            datetime_end = datetime.strptime(
                ' '.join([date_start, time_end]),
                '%Y-%m-%d %I:%M%p'
            )
        except Exception as e:
            raise ValidationError(_('Invalid end time'))

        # localize end time to org's timezone
        cleaned_data['datetime_end'] = pytz.timezone(tz).localize(datetime_end)

        # start time before end time
        if cleaned_data['datetime_end'] <= cleaned_data['datetime_start']:
            raise ValidationError(_(
                'Start time must be before end time'
            ))

        # end time in future
        if cleaned_data['datetime_end'] > datetime.now(tz=pytz.utc):
            raise ValidationError(_(
                'Submitted end time is in the future'
            ))

        # start time too far in past
        two_weeks_ago = datetime.now(tz=pytz.utc) - timedelta(weeks=2)
        if cleaned_data['datetime_start'] < two_weeks_ago:
            raise ValidationError(_(
                'You can submit hours for up to 2 weeks in the past'
            ))

        return cleaned_data


class EventCheckinForm(forms.Form):
    userid = forms.IntegerField()
    checkin = VolunteerCheckinField()


class BizDetailsForm(forms.Form):
    website = forms.URLField(
        widget=forms.TextInput(attrs={
            'placeholder': 'Website',
            'class': 'center',
        }),
        required=False
    )

    phone = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'Phone',
            'class': 'center',
        }),
        required=False
    )

    email = forms.EmailField(
        widget=forms.TextInput(attrs={
            'placeholder': 'Email',
            'class': 'center',
        }),
        required=False
    )

    address = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'Address',
            'class': 'center location',
        }),
        required=False
    )

    intro = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': ' '.join([
                'Introduce your business - What\'s your mission?',
                'What sets you apart?'
            ]),
            'rows': '3'
        }),
        required=False
    )

    def clean_phone(self):
        phone = self.cleaned_data['phone']

        if phone:
            phone = unicode.translate(
                phone,
                dict(
                    zip(
                        map(ord, string.punctuation),
                        [None for x in xrange(len(string.punctuation))]
                    )
                )
            )

            if not phone.isdigit():
                raise ValidationError(_('Invalid phone number'))

            if len(phone) < 10:
                raise ValidationError(_('Please enter phone area code'))

        return phone


class OfferCreateForm(forms.Form):
    def __init__(self, *args, **kwargs):
        orgid = kwargs.pop('orgid')
        self.org = Org.objects.get(id=orgid)
        super(OfferCreateForm, self).__init__(*args, **kwargs)

    offer_current_share = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'fit-left qtr-margin-right',
            'min': 0,
            'max': 100,
            'step': 1,
            'placeholder': 25,
            'value': 25
        })
    )

    offer_item = forms.CharField(
        validators=[MinLengthValidator(1)],
        widget=forms.TextInput(attrs={
            'class': 'good-cat',
            'placeholder': 'Item or category name',
            'value': 'All products and services'
        })
    )

    offer_limit_choice = forms.ChoiceField(
        widget=widgets.RadioWidget(attrs={
            'class': 'custom-radio'
        }),
        choices=[(0, 0), (1, 1)],
        initial=0
    )

    offer_limit_value = forms.IntegerField(
        widget=forms.NumberInput(attrs={'placeholder': 100}),
        initial=100,
        required=False
    )

    def clean_offer_current_share(self):
        offer_current_share = self.cleaned_data['offer_current_share']

        if offer_current_share < 5:
            raise ValidationError(_(
                'We require a minimum share of 5%'
            ))

        return int(offer_current_share)

    def clean_offer_item(self):
        offer_item = self.cleaned_data['offer_item']
        offer = Offer.objects.filter(
            org=self.org,
            item__name=offer_item
        )

        if offer:
            raise ValidationError(_(
                ' '.join([
                    'You\'ve already created an offer for this item.',
                    'Please edit the offer instead.'
                ])
            ))

        return offer_item

    def clean_offer_limit_choice(self):
        offer_limit_choice = self.cleaned_data['offer_limit_choice']

        if offer_limit_choice <= 0:
            raise ValidationError(_(
                'Monthly transaction limit must be greater than 0'
            ))

        return int(offer_limit_choice)

    def clean(self):
        cleaned_data = super(OfferCreateForm, self).clean()

        if cleaned_data['offer_limit_choice'] and \
            ('offer_limit_value' not in cleaned_data or \
                cleaned_data['offer_limit_value'] < 1):
            raise ValidationError(_('Invalid limit on transactions'))

        return cleaned_data


class OfferEditForm(OfferCreateForm):
    def __init__(self, *args, **kwargs):
        '''
        a) org from parent view
        b) existing offer
        '''
        offer_id = kwargs.pop('offer_id')
        self.offer_init = Offer.objects.get(id=offer_id)

        super(OfferEditForm, self).__init__(*args, **kwargs)

    def clean_offer_item(self):
        '''
        if offer item was changed, check there is not an existing offer
        '''

        offer_item = self.cleaned_data['offer_item']

        if self.offer_init.item.name != offer_item:
            offer = Offer.objects.filter(
                org=self.org,
                item__name=offer_item
            )

            if offer:
                raise ValidationError(_(
                    'You\'ve already created an offer for this item.'
                ))

        return offer_item


class RedeemCurrentsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        offer_id = kwargs.pop('offer_id')
        self.offer = Offer.objects.get(id=offer_id)
        self.user = kwargs.pop('user')

        super(RedeemCurrentsForm, self).__init__(*args, **kwargs)

    redeem_receipt = forms.ImageField(
         widget=forms.ClearableFileInput(attrs={
            'class': 'hidden-file',
            'id': 'upload-receipt',
            'accept': 'image/*'
        }),
        required=False
    )

    # redeem_receipt_if_checked = forms.BooleanField(
    #     widget=forms.CheckboxInput(attrs={
    #         'class': 'hidden',
    #         'id': 'receipt-if-checked'
    #     }),
    #     initial=True,
    # )

    redeem_no_proof = forms.CharField(
        required=False,
        widget= forms.Textarea(attrs={
            'class': 'hidden',
            'rows': '2',
            'placeholder': 'Details to help business identify your purchase'
        })
    )

    redeem_price = forms.DecimalField(
        widget=forms.NumberInput(),
        required=False
    )

    redeem_currents_amount = forms.FloatField(
        widget=forms.NumberInput(
            attrs={
                'class': 'hidden'
            }
        )
    )

    biz_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'id_biz_name',
            'class': 'center hidden',
        })
    )

    biz_name_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'biz_name_input',
            'class': 'center',
            'placeholder': 'What business are you using Currents with?'
        })
    )

    def clean(self):
        cleaned_data = super(RedeemCurrentsForm, self).clean()
        redeem_receipt = cleaned_data['redeem_receipt']
        redeem_no_proof = cleaned_data['redeem_no_proof']
        redeem_price = cleaned_data['redeem_price']

        user_balance_available = OcUser(self.user.id).get_balance_available()

        if user_balance_available <= 0:
            raise ValidationError(
                _('You don\'t have any currents to spend at this time')
            )

        if redeem_price <= 0:
            raise ValidationError(
                _('Invalid purchase price reported')
            )

        if redeem_receipt:
            content_type = redeem_receipt.content_type.split('/')[0]
            if content_type in settings.CONTENT_TYPES:
                if redeem_receipt._size > settings.MAX_UPLOAD_SIZE:
                    raise ValidationError(
                        _('Please keep image size under {}. Current size {}').format(
                            filesizeformat(settings.MAX_UPLOAD_SIZE),
                            filesizeformat(redeem_receipt._size)
                        )
                    )
            else:
                raise ValidationError(_('File type is not supported'))
        # comment out if no requirements for receipts or desc.
        elif not redeem_no_proof:
            raise ValidationError(
                _('Receipt or description of purchase is required')
            )

        return cleaned_data


class ConfirmGiftCardPurchaseForm(forms.Form):
    denomination = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'hidden'
        }),
        initial=25.0
    )

    biz_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'hidden',
        })
    )


class PublicRecordsForm(forms.Form):
    periods = (
        ('all-time', 'All-time'),
        ('month', 'Last 30 days'),
    )

    record_types = (
        ('top-org', 'Top organizations'),
        ('top-vol', 'Top volunteers'),
        ('top-biz', 'Top businesses'),
    )

    record_type = forms.ChoiceField(choices=record_types)
    period = forms.ChoiceField(choices=periods, required=False)


class PopUpAnswer(forms.Form):
    answer = forms.CharField(max_length=3, required=False)


# class HoursDetailsForm(forms.Form):

#     is_admin = forms.IntegerField(
#         widget=forms.HiddenInput(),
#         initial=0,
#         required=False
#         )

#     user_id = forms.IntegerField(
#         widget=forms.HiddenInput(),
#         initial=0,
#         required=False
#         )

#     hours_type = forms.CharField(
#         widget=forms.HiddenInput(),
#         max_length=10,
#         required=False
#         )


class ExportDataForm(forms.Form):
    """
    Export data to XLS form
        - define date_start and date_end form fields
        - validate date_start such that its a valid date
        - validate date_end such that its either empty or a valid date;
            empty field defaults to now (including today)
    """
    def __init__(self, *args, **kwargs):
        self.tz_org = kwargs.pop('tz_org')
        super(ExportDataForm, self).__init__(*args, **kwargs)

    # start_dt = datetime.now(self.tz_org) - timedelta(months=1)

    date_start = forms.CharField(
        label='Start date',
        widget=forms.TextInput(attrs={
            'id': 'start-date',
            'name': 'start-date',
            'placeholder': 'yyyy-mm-dd',
            # 'value': start_dt.strftime('%Y-%m-%d')
        })
    )

    date_end = forms.CharField(
        label='End date',
        widget=forms.TextInput(attrs={
            'id': 'end-date',
            'name': 'end-date',
            'placeholder': 'yyyy-mm-dd'
        })
    )

    def clean_date_start(self):
        date_start = self.cleaned_data['date_start']

        try:
            date_start = pytz.timezone(self.tz_org).localize(
                datetime.strptime(date_start, '%Y-%m-%d')
            )
        except Exception as e:
            raise ValidationError(_('Invalid start time'))

        return date_start

    def clean_date_end(self):
        date_end = self.cleaned_data['date_end']
        date_start_tomorrow = datetime.now(pytz.timezone(self.tz_org)).date()
        date_start_tomorrow += timedelta(days=1)

        if not date_end:
            return date_start_tomorrow

        try:
            date_end = pytz.timezone(self.tz_org).localize(
                datetime.strptime(date_end, '%Y-%m-%d')
            )
        except Exception as e:
            raise ValidationError(_('Invalid end time'))

        # cut-off at tomorrow if in the future
        if date_end.date() > date_start_tomorrow:
            date_end = date_start_tomorrow

        return date_end
