from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Login existing user form
class UserSignupForm(forms.Form):
    user_firstname = forms.CharField()
    user_lastname = forms.CharField()
    user_email = forms.EmailField()


# Login existing user form
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
