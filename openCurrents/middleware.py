from django.conf import settings
from django.contrib import auth
from datetime import datetime, timedelta
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

class AutoLogout(MiddlewareMixin):
    def process_request(self, request):
        if not request.user.is_authenticated() :
          #Can't log out if not logged in
          return

        try:
            time_now = datetime.strptime(datetime.now().isoformat(' '), "%Y-%m-%d %H:%M:%S.%f")
            time_sess = datetime.strptime(request.session['last_touch'], "%Y-%m-%d %H:%M:%S.%f")
            iddle_time = time_now - time_sess

            if  iddle_time > timedelta(0, settings.AUTO_LOGOUT_DELAY * 60, 0):
                request.session.pop('last_touch')
                auth.logout(request)
                return redirect('openCurrents:home')
        except KeyError:
            pass

        request.session['last_touch'] = datetime.now().isoformat(' ')


