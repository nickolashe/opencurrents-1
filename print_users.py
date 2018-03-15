import sys
from datetime import datetime, timedelta
from django.contrib.auth.models import User

args = sys.argv

print args

try:
    days_back = int(args[-1])
except:
    days_back = 7

delta = timedelta(days=days_back)
users = User.objects.filter(date_joined__gte=datetime.now() - delta)

for u in users:
    print u.id, \
        u.email, \
        u.usersettings.popup_reaction, \
        u.usersettings.monthly_updates, \
        u.date_joined.strftime('%Y-%m-%d'), \
        u.last_login.strftime('%Y-%m-%d') if u.last_login else None
