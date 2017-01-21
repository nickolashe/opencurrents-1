from django.shortcuts import render
from django.views.generic import View, TemplateView

# Create your views here.

class HomeView(TemplateView):
    template_name = 'home.html'

class ConfirmAccountView(TemplateView):
    template_name = 'confirm-account.html'

class CommunityView(TemplateView):
    template_name = 'community.html'

class LoginView(TemplateView):
    template_name = 'login.html'

class InviteFriendsView(TemplateView):
    template_name = 'invite-friends.html'

class ApproveHoursView(TemplateView):
    template_name = 'approve-hours.html'

class CausesView(TemplateView):
    template_name = 'causes.html'

class EditHoursView(TemplateView):
    template_name = 'edit-hours.html'

class FaqView(TemplateView):
    template_name = 'faq.html'

class FindOrgsView(TemplateView):
    template_name = 'find-orgs.html'

class GiveCurrentsView(TemplateView):
    template_name = 'give-currents.html'

class HoursApprovedView(TemplateView):
    template_name = 'hours-approved.html'

class InventoryView(TemplateView):
    template_name = 'Inventory.html'

class MissionView(TemplateView):
    template_name = 'mission.html'

class NominateView(TemplateView):
    template_name = 'nominate.html'

class NominationConfirmedView(TemplateView):
    template_name = 'nomination-confirmed.html'

class NominationEmailView(TemplateView):
    template_name = 'nomination-email.html'

class OrgHomeView(TemplateView):
    template_name = 'org-home.html'

class OrgSignupView(TemplateView):
    template_name = 'org-signup.html'

class RequestCurrentsView(TemplateView):
    template_name = 'request-currents.html'

class SellView(TemplateView):
    template_name = 'sell.html'

class SignupView(TemplateView):
    template_name = 'signup.html'

class TellYourBossView(TemplateView):
    template_name = 'tell-your-boss.html'

class UserHomeView(TemplateView):
    template_name = 'user-home.html'

class VerifyIdentityView(TemplateView):
    template_name = 'verify-identity.html'

class VolunteerHoursView(TemplateView):
    template_name = 'volunteer-hours.html'

class VolunteerRequestsView(TemplateView):
    template_name = 'volunteer-requests.html'
