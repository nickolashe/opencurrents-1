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

profile_url = reverse(
    'profile',
    urlconf=urls
)

invite_volunteers_url = reverse(
    'invite-volunteers',
    urlconf=urls
)

member_activity_url = reverse(
    'member-activity',
    urlconf=urls
)

url_signup = reverse(
    'process_signup',
    urlconf=urls,
    kwargs={'mock_emails': 1}
)

url_signup_endpoint = reverse(
    'process_signup',
    urlconf=urls,
    kwargs={'mock_emails': 1, 'endpoint': True}
)


def _get_url(id, url_string='', param_name_string=''):
    """
    Generate urls with kwargs.

    Takes string url_string and param_string, integer id and returns url.
    """
    url = reverse(
        url_string,
        urlconf=urls,
        kwargs={param_name_string: id}
    )

    return url


def event_detail_or_edit_url(event_id, edit=False):
    """
    Event-detail or event-edit url.

    Takes integer event_id, returns 'event-detail/x/' url if detail=True
    or returns 'edit-event/x/' url if detail=False
    """
    if not edit:
        url = _get_url(
            event_id,
            url_string='event-detail',
            param_name_string='pk'
        )
    else:
        url = _get_url(
            event_id,
            url_string='edit-event',
            param_name_string='event_id'
        )
    return url


def create_event_url(org_id):
    """
    Generate create-event url.

    Takes integer org_id, returns 'create-event/x/' url.
    """
    url = _get_url(
        org_id,
        url_string='create-event',
        param_name_string='org_id'
    )
    return url


def add_vols_to_past_event_url(event_ids):
    """
    Add volunteers to an event.

    Takes integer event_ids, returns 'invite-volunteers-past/x/' url.
    """
    url = _get_url(
        event_ids,
        url_string='invite-volunteers-past',
        param_name_string='event_ids'
    )
    return url


def redeem_currents_url(offer_id):
    """
    Add volunteers to an event.

    Takes integer offer_id, returns 'invite-volunteers-past/x/' url.
    """
    url = _get_url(
        offer_id,
        url_string='redeem-currents',
        param_name_string='offer_id'
    )
    return url
