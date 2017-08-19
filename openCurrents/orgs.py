class OrgUserInformation():
    def get_org_user(self, userid):
        org_user = OrgUser.objects.filter(user__id=userid)
        return org_user

    def get_user_org(self, userid):
        org_user = OrgUser.objects.filter(user__id=userid)
        return org_user[0].org

    def get_user_org_timezone(self, userid):
        org_user = OrgUser.objects.filter(user__id=userid)
        return org_user[0].org.timezone