from django.conf import settings
from django.contrib import auth
from django.contrib import messages
from datetime import datetime, timedelta
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class AutoLogout(MiddlewareMixin):

    def process_request(self, request):

        if not request.user.is_authenticated():
            # Can't log out if not logged in
            return

        try:
            time_now = datetime.strptime(datetime.now().isoformat(' '), "%Y-%m-%d %H:%M:%S.%f")
            time_sess = datetime.strptime(request.session['last_touch'], "%Y-%m-%d %H:%M:%S.%f")
            iddle_time = time_now - time_sess

            if iddle_time > timedelta(0, settings.AUTO_LOGOUT_DELAY * 60, 0):
                requested_page = request.META.get('PATH_INFO')

                request.session.pop('last_touch')
                auth.logout(request)

                messages.add_message(
                    request,
                    messages.ERROR,
                    "You've been logged out after {} minutes of inactivity".format(settings.AUTO_LOGOUT_DELAY),
                    extra_tags='alert'
                )

                # setting next page URL after login
                # preventing from cycling trhrough logout url
                if requested_page != '/process_logout/':
                    request.session['next'] = requested_page
                else:
                    request.session['next'] = None
                    requested_page = 'openCurrents:login'

                return redirect(requested_page)
        except KeyError:
            pass

        request.session['last_touch'] = datetime.now().isoformat(' ')
