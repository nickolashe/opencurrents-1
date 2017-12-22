from collections import OrderedDict
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

    def setup_orguser(self, org, is_admin=False):
        org_user = None

        try:
            org_user = OrgUser(
                org=org,
                user=self.user
            )
            org_user.save()
        except Exception as e:
            raise InvalidOrgUserException()

        if is_admin:
            self.make_org_admin(org.id)

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

    def get_admin_group(self, orgid):
        admin_org_group_name = '_'.join(['admin', str(orgid)])

        admin_org_group = None
        try:
            admin_org_group = Group.objects.get(
                name=admin_org_group_name
            )
        except Exception as e:
            logger.warning('org %d without admin group', orgid)

        return admin_org_group

    def is_org_admin(self, orgid):
        admin_group = self.get_admin_group(orgid)
        if admin_group and admin_group.user_set.filter(id=self.userid):
            return True
        else:
            return False

    def make_org_admin(self, orgid):
        admin_group = self.get_admin_group(orgid)
        if admin_group:
            try:
                admin_group.user_set.add(self.user)
            except Exception:
                logger.warning(
                    'user %s is already admin of org %d',
                    self.user.username,
                    orgid
                )
        else:
            logger.warning('org %d without admin group', orgid)
            raise InvalidOrgException()

    def is_user_in_org_group(self):
        in_group = Group.objects.filter(user=self.user)
        return True if in_group else False


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
            self.orgid = org.id
        except Exception as e:
            raise OrgExistsException

        OrgEntity.objects.create(org=org)

        Group.objects.create(name='admin_%s' % org.id)
        return org

    def get_top_issued_npfs(self, period, quantity=10):
        result = list()
        orgs = Org.objects.filter(status='npf')

        for org in orgs:
            issued_cur_amount = OcLedger().get_issued_cur_amount(org.id, period)['total']
            if not issued_cur_amount:
                issued_cur_amount = 0
            result.append({'name': org.name, 'total': issued_cur_amount})

        result.sort(key=lambda org_dict: org_dict['total'], reverse=True)
        return result[:quantity]

    def get_top_accepted_bizs(self, period, quantity=10):
        result = list()
        bizs = Org.objects.filter(status='biz')

        for biz in bizs:
            accepted_cur_amount = OcLedger().get_accepted_cur_amount(biz.id, period)['total']
            if not accepted_cur_amount:
                accepted_cur_amount = 0
            result.append({'name': biz.name, 'total': accepted_cur_amount})

        result.sort(key=lambda biz_dict: biz_dict['total'], reverse=True)
        return result[:quantity]


class InvalidOrgException(Exception):
    pass


class OrgExistsException(Exception):
    pass


class ExistingAdminException(Exception):
	pass


class InvalidOrgUserException(Exception):
    pass
