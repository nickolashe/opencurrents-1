from django.contrib.auth.models import Group
from openCurrents.models import \
    Org, \
    OrgUser, \
    OrgEntity, \
    Account

from openCurrents.interfaces.ocuser import OcUser

import logging

logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OrgUserInfo(object):
    def __init__(self, userid):
        self.userid = userid
        self.orgusers = OrgUser.objects.filter(user__id=userid)

    def setup_orguser(self, org, affiliation=None):
        org_user = None
        user=OcUser(self.userid).get_user()

        try:
            org_user = OrgUser(
                org=org,
                user=user,
                affiliation=affiliation
            )
            org_user.save()
        except Exception as e:
            logger.error(e)
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
        admin_org_group_name = ['_'.join(['admin', str(orgid)])]
        admin_org_group = Group.objects.filter(
            name__in=admin_org_group_name,
            user__id=self.userid
        ).exists()
        return True if admin_org_group else False


class OcOrg(object):
    def __init__(self, orgid=None):
        self.orgid = orgid

    def setup_org(self, name, status, website=None):
        org = None
        try:
            org = Org(
                name=name,
                website=website,
                status=status
            )
            org.save()
        except Exception as e:
            raise OrgExistsException

        org_account = Account()
        org_account.save()

        OrgEntity.objects.create(org=org, account=org_account)

        return org


class OrgExistsException(Exception):
	pass

class InvalidOrgUserException(Exception):
	pass
