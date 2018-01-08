from django.contrib.auth.models import Group
from openCurrents.models import Org
from openCurrents.interfaces.orgs import OrgUserInfo


class OcAuth(object):
    def __init__(self, userid):
        self.userid = userid
        orguserinfo = OrgUserInfo(userid)
        self.org = orguserinfo.get_org()

    def is_admin(self, org_id=None):
    	'''
    	returns true if user has admin affiliation with their org
    	'''
        is_admin = False

        if org_id:
        	org = Org.objects.get(id=org_id)
        elif self.org:
    		org = self.org
    	else:
    		return False

        admin_org_group_name = '_'.join(['admin', str(org.id)])

        admin_org_group = Group.objects.filter(
            name=admin_org_group_name,
            user__id=self.userid
        )

        if admin_org_group:
            is_admin = True

        return is_admin

    def is_admin_org(self):
    	'''
    	returns true if user is an admin of a non-profit
    	'''
    	return self.is_admin() and self.org.status == 'npf'

    def is_admin_biz(self):
    	'''
    	returns true if user is an admin of a business
    	'''
    	return self.is_admin() and self.org.status == 'biz'
