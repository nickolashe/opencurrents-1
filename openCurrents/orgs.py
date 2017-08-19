class OrgUserInfo(object):
    def __init__(self, userid):
        self.userid = userid
        self.orgusers = OrgUser.objects.filter(user__id=userid)

    def get_orguser(self):
        return self.orgusers ? self.orgusers[0] : None

    def get_org(self):
        return self.orgusers ? self.orgusers[0].org : None

    def get_org_timezone(self, userid):
        return self.orgusers ? self.orgusers[0].org.timezone : None
