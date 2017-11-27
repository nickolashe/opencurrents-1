from django.contrib.auth.models import Group
from openCurrents.models import \
    Org, \
    OrgUser, \
    OrgEntity

from openCurrents.interfaces.ocuser import OcUser
from openCurrents.interfaces.ledger import OcLedger

import logging

logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OrgUserInfo(object):
    def __init__(self, userid):
        self.userid = userid
        self.user=OcUser(self.userid).get_user()
        self.orgusers = OrgUser.objects.filter(user__id=userid)

    def setup_orguser(self, org, affiliation=None):
        org_user = None

        try:
            org_user = OrgUser(
                org=org,
                user=self.user,
                affiliation=affiliation
            )
            org_user.save()
        except Exception as e:
            raise InvalidOrgUserException()

        return org_user

    def get_orguser(self):
        return self.orgusers if self.orgusers else []

    def get_org(self):
        return self.orgusers[0].org if self.orgusers else None

    def get_org_id(self):
        return self.orgusers[0].org.id if self.orgusers else None

    def get_org_name(self):
        return self.orgusers[0].org.name if self.orgusers else None

    def get_org_timezone(self):
        return self.orgusers[0].org.timezone if self.orgusers else 'America/Chicago'

    def is_org_admin(self, orgid):
        admin_org_group_name = '_'.join(['admin', str(orgid)])
        admin_org_group = Group.objects.filter(
            name=admin_org_group_name,
            user__id=self.userid
        ).exists()
        return True if admin_org_group else False

    def make_org_admin(self, orgid):
        admin_org_group_name = '_'.join(['admin', str(orgid)])
        admin_org_group = Group.objects.filter(
            name=admin_org_group_name
        )
        if admin_org_group:
            try:
                admin_org_group[0].user_set.add(self.user)
            except Exception:
                raise ExistingAdminException()
        else:
            raise InvalidOrgException()


class OcOrg(object):
    def __init__(self, orgid=None):
        self.orgid = orgid

        if self.orgid:
            try:
                self.org = Org.objects.get(id=self.orgid)
            except Exception as e:
                raise InvalidOrgException

    def setup_org(self, name, status, website=None):
        org = None
        try:
            org = Org(
                name=name,
                status=status,
                website=website
            )
            org.save()
        except Exception as e:
            raise OrgExistsException

        OrgEntity.objects.create(org=org)

        Group.objects.create(name='admin_%s' % org.id)
        return org


class InvalidOrgException(Exception):
	pass


class OrgExistsException(Exception):
	pass


class ExistingAdminException(Exception):
	pass


class InvalidOrgUserException(Exception):
	pass
