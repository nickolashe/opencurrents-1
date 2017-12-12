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
    Ledger, \
    UserEventRegistration

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


def _create_test_user(user_name, password = 'password', org = None,  is_org_admin=False):
    """
    Creates users and maps them to the org if needed.
    Takes:
        user_name - string

        org - Org object. A NPF admin will be created, if Org is provided and is_org_admin = True.
        An org user will be created if org is provided and is_org_admin = False.
        If no org provided - a volunteer will be created.

        is_org_admin - if True, the user will be made an org admin, if org is provided.
    """

    test_user = OcUser().setup_user(
        username = user_name,
        email = user_name+'@email.cc',
        first_name=user_name + '_first_name',
        last_name= user_name + '_last_name'
    )

    if org:
        # mapping user to org
        oui = OrgUserInfo(test_user.id)
        oui.setup_orguser(org)

        # making a user an org admin
        if is_org_admin:
            oui.make_org_admin(org.id)

    test_user.set_password(password)
    test_user.save()
    return test_user


def _create_project(org, project_name):
    """
    org - Org object
    project_name - string
    """

    project = Project(
        org=org,
        name=project_name
    )
    project.save()
    return project


def _create_event(
        project,
        datetime_start,
        datetime_end,
        description="Test Event",
        location="test_location",
        is_public=False,
        event_type="MN",
        coordinator=None,
        creator_id = None
    ):

    event = Event(
        project=project,
        description=description,
        location=location,
        is_public=is_public,
        datetime_start=datetime_start,
        datetime_end=datetime_end,
        coordinator=coordinator,
        creator_id=creator_id
    )
    event.save()
    return event


def _setup_user_event_registration(
        user,
        event,
        is_confirmed=True
    ):

    user_event_registration = UserEventRegistration(
        user=user,
        event=event,
    )
    user_event_registration.save()
    return user_event_registration


def _setup_volunteer_hours(volunteer, npf_admin, org, project, datetime_start, datetime_end, description="Manually tracked time ", event_type="MN", is_verified = False, action_type = 'req'):
    """
    function takes:
        volunteer = User objects
        npf_admin = npf admin object
        org = Org object
        project = Project object
        description = provided string will be added to the end of default string
        event_type = string "MN" or "GR" (defautl "MN")
        datetime_start = datetime.datetime
        datetime_end = datetime.datetime
        is_verified = False/True (default False)
        action_type = 'app'/'dec'/'req' (default 'req')
    and creates respective records in testing DB.
    """
    event = Event.objects.create(
        project=project,
        is_public = True,
        description="finished event",
        location="test_location",
        coordinator=npf_admin,
        event_type=event_type,
        datetime_start=datetime_start,
        datetime_end=datetime_end
    )

    volunteer_timelog = UserTimeLog.objects.create(
        user=volunteer,
        event=event,
        datetime_start=datetime_start,
        datetime_end=datetime_end,
        is_verified=is_verified
    )

    actiontimelog = AdminActionUserTime.objects.create(
        user=npf_admin,
        usertimelog=volunteer_timelog,
        action_type=action_type
    )

