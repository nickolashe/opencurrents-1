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


def event_detail_or_edit_url(event_id, edit=False):
    """
    Event-detail or event-edit url.

    Takes integer event_id, returns 'event-detail/x/' url if detail=True
    or returns 'edit-event/x/' url if detail=False
    """
    if not edit:
        event_url = reverse(
            'event-detail',
            urlconf=urls,
            kwargs={'pk': event_id}
        )

    else:
        event_url = reverse(
            'edit-event',
            urlconf=urls,
            kwargs={'event_id': event_id}
        )

    return event_url


def create_event_url(org_id):
    """
    Generate create-event url.

    Takes integer org_id, returns 'create-event/x/' url.
    """
    create_event_url = reverse(
        'create-event',
        urlconf=urls,
        kwargs={'org_id': org_id}
    )

    return create_event_url


def add_vols_to_past_event_url(event_ids):
    """
    Add volunteers to an event.

    Takes integer event_ids, returns 'invite-volunteers-past/x/' url.
    """
    add_vols_to_past_event_url = reverse(
        'invite-volunteers-past',
        urlconf=urls,
        kwargs={'event_ids': event_ids}
    )

    return add_vols_to_past_event_url
