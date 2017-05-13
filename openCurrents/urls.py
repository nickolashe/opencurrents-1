from django.conf.urls import url, include
from openCurrents import views

urlpatterns = [
    # template views
    url(r'^$', views.HomeView.as_view(), name='root'),
    url(r'^home/$', views.HomeView.as_view(), name='home'),
    url(r'^home/(?P<referrer>[\w\.@\+\-]*)$', views.HomeView.as_view(), name='home'),
    url(r'^home/(?P<referrer>[\w\.@\+\-]*)/(?P<status_msg>.*)/$', views.HomeView.as_view(), name='home'),
    url(r'^invite/(?P<referrer>[\w\.@\+\-]*)$', views.HomeView.as_view(), name='invite'),
    url(r'^confirm-account/(?P<email>[\w\.@\+\-]+)/$', views.ConfirmAccountView.as_view(), name='confirm-account'),
    url(r'^confirm-account/(?P<email>[\w\.@\+\-]+)/(?P<status_msg>.*)/$', views.ConfirmAccountView.as_view(), name='confirm-account'),
    url(r'^confirm-account/(?P<email>[\w\.@\+\-]+)/(?P<token>\w{8}-\w{4}-\w{4}-\w{4}-\w{12})/$', views.ConfirmAccountView.as_view(), name='confirm-account'),
    url(r'^community$', views.CommunityView.as_view(), name='community'),
    url(r'^login/$', views.LoginView.as_view(), name='login'),
    url(r'^login/(?P<status_msg>.*)$', views.LoginView.as_view(), name='login'),
    url(r'^invite-friends/(?P<referrer>[\w\.@\+\-]*)$', views.InviteFriendsView.as_view(), name='invite-friends'),
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
	url(r'^org-signup/$', views.OrgSignupView.as_view(), name='org-signup'),
    url(r'^org-signup/(?P<org_name>.*)/$', views.OrgSignupView.as_view(), name='org-signup'),
	url(r'^org-signup/(?P<org_name>.*)/(?P<status_msg>.*)/$', views.OrgSignupView.as_view(), name='org-signup'),
	url(r'^request-currents$', views.RequestCurrentsView.as_view(), name='request-currents'),
	url(r'^sell$', views.SellView.as_view(), name='sell'),
	url(r'^signup/$', views.SignupView.as_view(), name='signup'),
	url(r'^signup/(?P<status_msg>.*)/$', views.SignupView.as_view(), name='signup'),
	url(r'^org-approval$', views.OrgApprovalView.as_view(), name='org-approval'),
	url(r'^user-home/$', views.UserHomeView.as_view(), name='user-home'),
	url(r'^user-home/(?P<status_msg>.*)/$', views.UserHomeView.as_view(), name='user-home'),
	url(r'^verify-identity$', views.VerifyIdentityView.as_view(), name='verify-identity'),
	url(r'^volunteer-hours$', views.VolunteerHoursView.as_view(), name='volunteer-hours'),
	url(r'^volunteering$', views.VolunteeringView.as_view(), name='volunteering'),
	url(r'^volunteer-requests$', views.VolunteerRequestsView.as_view(), name='volunteer-requests'),
	url(r'^profile$', views.ProfileView.as_view(), name='profile'),
	url(r'^edit-profile$', views.EditProfileView.as_view(), name='edit-profile'),
	url(r'^blog$', views.BlogView.as_view(), name='blog'),
	url(r'^create-project$', views.CreateProjectView.as_view(), name='create-project'),
	url(r'^project-details$', views.ProjectDetailsView.as_view(), name='project-details'),
	url(r'^invite-volunteers$', views.InviteVolunteersView.as_view(), name='invite-volunteers'),
	url(r'^project-created$', views.ProjectCreatedView.as_view(), name='project-created'),


    # functional views
    url(r'^process_login/$', views.process_login, name='process_login'),
    url(r'^process_logout/$', views.process_logout, name='process_logout'),
    url(r'^process_signup/(?P<referrer>[\w\.@\+\-]*)$', views.process_signup, name='process_signup'),
    url(r'^process_email_confirmation/(?P<user_email>[\w\.@\+\-]+)/$', views.process_email_confirmation, name='process_email_confirmation'),
    url(r'^process_org_signup/$', views.process_org_signup, name='process_org_signup')
]

#handler404 = 'openCurrents.views.return_404'
