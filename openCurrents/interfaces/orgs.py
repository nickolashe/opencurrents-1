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
        self.orgusers = OrgUser.objects.filter(user__id=userid)

    def setup_orguser(self, org, affiliation=None):
        org_user = None
        user = OcUser(self.userid).get_user()

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
                website=website,
                status=status
            )
            org.save()
        except Exception as e:
            logger.error(e)
            raise OrgExistsException

        OrgEntity.objects.create(org=org)

        return org

    def get_top_issued_npfs(self, period):
        result = list()
        orgs = Org.objects.filter(status='npf').select_related('orgentity')

        for org in orgs:
            issued_cur_amount = OcLedger().get_issued_cur_amount(org.id, period)
            if not issued_cur_amount['total']:
                issued_cur_amount['total'] = 0
            result.append({'name': org.name, 'total': issued_cur_amount['total']})

        result.sort(key=lambda org_dict: org_dict['total'], reverse=True)
        return result[:10]

    def get_top_accepted_bizs(self, period):
        result = list()
        bizs = Org.objects.filter(status='biz').select_related('orgentity')

        for biz in bizs:
            accepted_cur_amount = OcLedger().get_accepted_cur_amount(biz.id, period)
            if not accepted_cur_amount['total']:
                accepted_cur_amount['total'] = 0
            result.append({'name': biz.name, 'total': accepted_cur_amount['total']})

        result.sort(key=lambda biz_dict: biz_dict['total'], reverse=True)
        return result[:10]


class InvalidOrgException(Exception):
    pass


class OrgExistsException(Exception):
    pass


class InvalidOrgUserException(Exception):
    pass
