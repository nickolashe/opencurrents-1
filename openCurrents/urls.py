from django.conf.urls import url, include
from openCurrents import views

urlpatterns = [
    # template views
    url(r'^$', views.HomeView.as_view(), name='root'),
    url(r'^home$', views.HomeView.as_view(), name='home'),
    url(r'^confirm-account$', views.ConfirmAccountView.as_view(), name='confirm-account'),
    url(r'^community$', views.CommunityView.as_view(), name='community'),
    url(r'^login$', views.LoginView.as_view(), name='login'),
    url(r'^invite-friends$', views.InviteFriendsView.as_view(), name='invite-friends'),
    url(r'^approve-hours$', views.ApproveHoursView.as_view(), name='approve-hours'),
	url(r'^causes$', views.CausesView.as_view(), name='causes'), 
	url(r'^edit-hours$', views.EditHoursView.as_view(), name='edit-hours'),
	url(r'^faq$', views.FaqView.as_view(), name='faq'),
	url(r'^find-orgs$', views.FindOrgsView.as_view(), name='find-orgs'),
	url(r'^give-currents$', views.GiveCurrentsView.as_view(), name='give-currents'),
	url(r'^hours-approved$', views.HoursApprovedView.as_view(), name='hours-approved'),
	url(r'^inventory$', views.InventoryView.as_view(), name='inventory'),
	url(r'^mission$', views.MissionView.as_view(), name='mission'),
	url(r'^nominate$', views.NominateView.as_view(), name='nominate'),
	url(r'^nomination-confirmed$', views.NominationConfirmedView.as_view(), name='nomination-confirmed'),
	url(r'^nomination-email$', views.NominationEmailView.as_view(), name='nomination-email'),
	url(r'^org-signup$', views.OrgSignupView.as_view(), name='org-signup'),
	url(r'^request-currents$', views.RequestCurrentsView.as_view(), name='request-currents'),
	url(r'^sell$', views.SellView.as_view(), name='sell'),
	url(r'^signup$', views.SignupView.as_view(), name='signup'),
	url(r'^tell-your-boss$', views.TellYourBossView.as_view(), name='tell-your-boss'),
	url(r'^user-home$', views.UserHomeView.as_view(), name='user-home'),
	url(r'^verify-identity$', views.VerifyIdentityView.as_view(), name='verify-identity'),
	url(r'^volunteer-hours$', views.VolunteerHoursView.as_view(), name='volunteer-hours'),
	url(r'^volunteer-requests$', views.VolunteerRequestsView.as_view(), name='volunteer-requests'),

    # functional views
    #url(r'^assign_credit_to_user/$', views.assign_credit_to_user, name='assign_credit_to_user')
]

#handler404 = 'openCurrents.views.return_404'
