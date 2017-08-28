from django.contrib.auth.models import Group
from openCurrents.models import \
    OrgUser

class OrgUserInfo(object):
    def __init__(self, userid):
        self.userid = userid
        self.orgusers = OrgUser.objects.filter(user__id=userid)

    def get_orguser(self):
        return self.orgusers if self.orgusers else []

    def get_org(self):
        return self.orgusers[0].org if self.orgusers else None

    def get_org_id(self):
        return self.orgusers[0].org.id if self.orgusers else None

    def get_org_name(self):
        return self.orgusers[0].org.name if self.orgusers else None

    def get_org_timezone(self, userid):
        return self.orgusers[0].org.timezone if self.orgusers else 'America/Chicago'

    def is_org_admin(self, orgid):
        admin_org_group_name = ['_'.join(['admin', str(orgid)])]
        admin_org_group = Group.objects.filter(
            name__in=admin_org_group_name,
            user__id=self.userid
        ).exists()
        return True if admin_org_group else False
