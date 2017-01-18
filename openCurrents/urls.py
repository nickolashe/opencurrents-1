from django.conf.urls import url, include
from openCurrents import views

urlpatterns = [
    # template views
    url(r'^$', views.HomeView.as_view(), name='root'),
    url(r'^home$', views.HomeView.as_view(), name='home'),
    url(r'^confirm-account$', views.ConfirmAccountView.as_view(), name='confirm-account'),
    url(r'^community$', views.CommunityView.as_view(), name='community'),
    url(r'^login$', views.LoginView.as_view(), name='login'),
    url(r'^invite-friends$', views.InviteFriendsView.as_view(), name='invite-friends')

    # functional views
    #url(r'^assign_credit_to_user/$', views.assign_credit_to_user, name='assign_credit_to_user')
]

#handler404 = 'openCurrents.views.return_404'
