from django.conf.urls import url, include
from openCurrents import views

urlpatterns = [
    # template views
    url(r'^$', views.HomeView.as_view(), name='root'),
    url(r'^home$', views.HomeView.as_view(), name='home'),

    # functional views
    #url(r'^assign_credit_to_user/$', views.assign_credit_to_user, name='assign_credit_to_user')
]

#handler404 = 'openCurrents.views.return_404'
