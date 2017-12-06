from django.contrib.auth.models import User

from datetime import datetime, timedelta
from django.utils import timezone

from openCurrents.models import \
    Org, \
    Entity, \
    UserEntity, \
    OrgEntity, \
    OrgUser, \
    Project, \
    Event, \
    UserTimeLog, \
    AdminActionUserTime, \
    Ledger

from openCurrents.interfaces.ocuser import \
    OcUser, \
    InvalidUserException, \
    UserExistsException

from openCurrents.interfaces.orgs import \
    OrgUserInfo

from openCurrents.interfaces.orgadmin import OrgAdmin

from openCurrents.interfaces.common import diffInHours

import pytz
import uuid
import random
import string
import re


# @@ TODO @@
# finish this file
#
# WORK IN PROGRESS HERE !!!!
# do not use this file yet
#


def _create_test_user(user_name, org, is_org_user=False, is_org_admin=False, password = 'password'):
        """
        users and maps them to the org if needed.
        user_name - string
        if is_org_user = True, the user will be mapped to the org
        if is_org_admin = True, the user will be made an org admin
        org - Org object
        """

        org_user = OcUser().setup_user(
            username = user_name,
            email = user_name+'@email.cc',
            first_name=user_name + '_first_name',
            last_name= user_name + '_last_name'
        )

        if is_org_user:
            # mapping user to org
            oui = OrgUserInfo(org_user.id)
            oui.setup_orguser(org)

            # making a user an org admin
            if is_org_admin:
                oui.make_org_admin(org.id)

        org_user.set_password(password)
        org_user.save()
'''
def _setup_hours(volunteer, npf_admin, project ..... ):
    """
    Takes:
    volunteer =
    npf_admin =
    org =
    project =
    description =
    event_type =
    datetime_start =
    datetime_end =
    is_verified =
    action_type =

    and creates respective records in testing DB.
    """

    volunteer1 = User.objects.get(username='volunteer_1')
    datetime_start = past_date + timedelta(hours=2)
    datetime_end = past_date + timedelta(hours=6)

    project = Project.objects.create(
        org=org,
        name="test_project_2"
    )

    volunteer1_mt_event_1 = Event.objects.create(
        project=project,
        is_public = True,
        description="finished event",
        location="test_location_4",
        coordinator=org_admin,
        event_type="MN",
        datetime_start=datetime_start,
        datetime_end=datetime_end
    )

    volunteer1_timelog = UserTimeLog.objects.create(
        user=volunteer1,
        event=volunteer1_mt_event_1,
        datetime_start=datetime_start,
        datetime_end=datetime_end,
        is_verified=True
    )

    actiontimelog = AdminActionUserTime.objects.create(
        user=org_admin,
        usertimelog=volunteer1_timelog,
        action_type='app'
    )
'''
