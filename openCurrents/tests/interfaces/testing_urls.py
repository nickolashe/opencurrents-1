"""Collection of the urls that are called in unit tests."""

from django.core.urlresolvers import reverse
from openCurrents import views, urls

org_admin_url = reverse(
    'org-admin',
    urlconf=urls
)

export_data_url = reverse(
    'export-data',
    urlconf=urls
)
