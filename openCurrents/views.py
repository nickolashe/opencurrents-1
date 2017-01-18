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
