from openCurrents.models import \
    OrgUser

class OrgUserInfo(object):
    def __init__(self, userid):
        self.userid = userid
        self.orgusers = OrgUser.objects.filter(user__id=userid)

    def get_orguser(self):
        return self.orgusers if self.orgusers else None

    def get_org(self):
        return self.orgusers[0].org if self.orgusers else None

    def get_org_timezone(self, userid):
        return self.orgusers[0].org.timezone if self.orgusers else None
