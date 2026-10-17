from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from config.jsonutil import read_json

from .models import Option, Poll, Vote

PAGE_SIZE = 10


def index(request):
    return render(request, "index.html")


def _poll_queryset():
    """Polls with author, options and per-option vote counts in 2 queries."""
    options = Option.objects.annotate(vote_count=Count("votes")).order_by("position", "id")
    return Poll.objects.select_related("author").prefetch_related(Prefetch("options", queryset=options))


def _my_votes(request, polls):
    """Map poll id -> option id for the logged-in user (one query, none for anonymous)."""
    if not request.user.is_authenticated or not polls:
        return {}
    rows = Vote.objects.filter(user=request.user, poll_id__in=[p.id for p in polls])
    return dict(rows.values_list("poll_id", "option_id"))


def serialize_poll(poll, my_vote=None):
    options = list(poll.options.all())
    total = sum(option.vote_count for option in options)
    return {
        "id": poll.id,
        "question": poll.question,
        "author": poll.author.username,  # never expose the email
        "created_at": poll.created_at.isoformat(),
        "total_votes": total,
        "options": [
            {
                "id": option.id,
                "text": option.text,
                "votes": option.vote_count,
                "percent": round(option.vote_count * 100 / total) if total else 0,
            }
            for option in options
        ],
        "my_vote": my_vote,
    }


@require_GET
def poll_list(request):
    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        page = 1
    start = (page - 1) * PAGE_SIZE
    # Fetch one extra row to learn whether another page exists without a COUNT query.
    rows = list(_poll_queryset()[start : start + PAGE_SIZE + 1])
    has_next = len(rows) > PAGE_SIZE
    polls = rows[:PAGE_SIZE]
    my_votes = _my_votes(request, polls)
    return JsonResponse(
        {
            "polls": [serialize_poll(p, my_votes.get(p.id)) for p in polls],
            "page": page,
            "has_next": has_next,
        }
    )


@require_GET
def poll_detail(request, poll_id):
    poll = _poll_queryset().filter(pk=poll_id).first()
    if poll is None:
        raise Http404
    return JsonResponse(serialize_poll(poll, _my_votes(request, [poll]).get(poll.id)))


@require_POST
def poll_vote(request, poll_id):
    poll = get_object_or_404(Poll, pk=poll_id)
    data = read_json(request) or {}
    option_id = data.get("option_id")
    option = None
    if isinstance(option_id, int) and not isinstance(option_id, bool):
        option = Option.objects.filter(pk=option_id, poll=poll).first()
    if option is None:
        return JsonResponse({"errors": {"option_id": ["Geçerli bir seçenek seç."]}}, status=400)

    with transaction.atomic():
        if request.user.is_authenticated:
            # One vote per user per poll: voting again changes the earlier choice.
            Vote.objects.update_or_create(poll=poll, user=request.user, defaults={"option": option})
        else:
            # Anonymous votes carry no identity; repeat votes are only discouraged client-side.
            Vote.objects.create(poll=poll, option=option)

    fresh = _poll_queryset().get(pk=poll.pk)
    return JsonResponse(serialize_poll(fresh, option.id if request.user.is_authenticated else None))
