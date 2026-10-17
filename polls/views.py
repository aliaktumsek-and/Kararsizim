from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from config.jsonutil import read_json
from ratelimit.utils import POLL_CREATE, VOTE_ANON, VOTE_MEMBER, client_ip, hit, too_many

from .models import MAX_OPTIONS, MIN_OPTIONS, OPTION_MAX_LENGTH, QUESTION_MAX_LENGTH, Option, Poll, Vote

PAGE_SIZE = 10


def index(request):
    return render(request, "index.html")


@login_required
@ensure_csrf_cookie
def create_page(request):
    return render(request, "create.html")


def detail_page(request, poll_id):
    poll = get_object_or_404(Poll, pk=poll_id)
    return render(request, "poll_detail.html", {"poll": poll})


def _closed_response(poll, request):
    """409 with the current poll so the client can redraw it as closed."""
    fresh = _poll_queryset().get(pk=poll.pk)
    mine = _my_votes(request, [fresh]).get(fresh.id)
    return JsonResponse(
        {"errors": {"__all__": ["Bu anket kapandı, artık oy verilemez."]}, "poll": serialize_poll(fresh, mine)},
        status=409,
    )


def _not_found():
    return JsonResponse({"errors": {"__all__": ["Anket bulunamadı."]}}, status=404)


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
        "is_closed": poll.is_closed,
        # Automatic deadline, only meaningful while the poll is still open.
        "closes_at": None if poll.is_closed else poll.expires_at.isoformat(),
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


def poll_list(request):
    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        page = 1
    start = (page - 1) * PAGE_SIZE
    queryset = _poll_queryset()
    if request.GET.get("status") == "closed":
        queryset = queryset.closed()
    if request.GET.get("sort") == "popular":
        queryset = queryset.annotate(vote_total=Count("votes")).order_by("-vote_total", "-created_at", "-id")
    # Fetch one extra row to learn whether another page exists without a COUNT query.
    rows = list(queryset[start : start + PAGE_SIZE + 1])
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


def poll_detail(request, poll_id):
    poll = _poll_queryset().filter(pk=poll_id).first()
    if poll is None:
        return _not_found()
    return JsonResponse(serialize_poll(poll, _my_votes(request, [poll]).get(poll.id)))


def poll_delete(request, poll_id):
    if not request.user.is_authenticated:
        return JsonResponse({"errors": {"__all__": ["Anketi silmek için giriş yapmalısın."]}}, status=401)
    poll = Poll.objects.filter(pk=poll_id).first()
    if poll is None:
        return _not_found()
    if poll.author_id != request.user.id:
        return JsonResponse({"errors": {"__all__": ["Sadece kendi anketini silebilirsin."]}}, status=403)
    poll.delete()  # options and votes are removed by cascade
    return HttpResponse(status=204)


@require_http_methods(["GET", "DELETE"])
def poll_item(request, poll_id):
    """/api/polls/<id>/: GET returns one poll, DELETE removes it (author only)."""
    if request.method == "DELETE":
        return poll_delete(request, poll_id)
    return poll_detail(request, poll_id)


@require_POST
def poll_vote(request, poll_id):
    poll = Poll.objects.filter(pk=poll_id).first()
    if poll is None:
        return _not_found()
    if poll.is_closed:
        return _closed_response(poll, request)
    data = read_json(request) or {}
    option_id = data.get("option_id")
    option = None
    if isinstance(option_id, int) and not isinstance(option_id, bool):
        option = Option.objects.filter(pk=option_id, poll=poll).first()
    if option is None:
        return JsonResponse({"errors": {"option_id": ["Geçerli bir seçenek seç."]}}, status=400)

    # Rate limit only votes that would actually be stored. Members are limited by
    # account; anonymous visitors by a short-lived keyed hash of their IP, which is
    # never stored with the vote itself.
    if request.user.is_authenticated:
        wait = hit(VOTE_MEMBER, str(request.user.id))
    else:
        wait = hit(VOTE_ANON, client_ip(request))
    if wait:
        return too_many(wait)

    with transaction.atomic():
        if request.user.is_authenticated:
            # One vote per user per poll: voting again changes the earlier choice.
            Vote.objects.update_or_create(poll=poll, user=request.user, defaults={"option": option})
        else:
            # Anonymous votes carry no identity; repeat votes are only discouraged client-side.
            Vote.objects.create(poll=poll, option=option)

    fresh = _poll_queryset().get(pk=poll.pk)
    return JsonResponse(serialize_poll(fresh, option.id if request.user.is_authenticated else None))


def _validate_new_poll(data):
    """Return (question, options, errors) for a create-poll payload."""
    errors = {}

    question = data.get("question")
    question = question.strip() if isinstance(question, str) else ""
    if not question:
        errors["question"] = ["Soru boş olamaz."]
    elif len(question) > QUESTION_MAX_LENGTH:
        errors["question"] = [f"Soru en fazla {QUESTION_MAX_LENGTH} karakter olabilir."]

    raw_options = data.get("options")
    options = []
    if not isinstance(raw_options, list):
        errors["options"] = ["Seçenekler gönderilmedi."]
    else:
        options = [o.strip() if isinstance(o, str) else "" for o in raw_options]
        problems = []
        if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
            problems.append(f"Anket için {MIN_OPTIONS} ile {MAX_OPTIONS} arasında seçenek eklemelisin.")
        if any(not o for o in options):
            problems.append("Seçenekler boş olamaz.")
        if any(len(o) > OPTION_MAX_LENGTH for o in options):
            problems.append(f"Her seçenek en fazla {OPTION_MAX_LENGTH} karakter olabilir.")
        filled = [o.casefold() for o in options if o]
        if len(filled) != len(set(filled)):
            problems.append("Aynı seçenek birden fazla kez eklenmiş.")
        if problems:
            errors["options"] = problems

    return question, options, errors


@require_POST
def poll_create(request):
    if not request.user.is_authenticated:
        return JsonResponse({"errors": {"__all__": ["Anket oluşturmak için giriş yapmalısın."]}}, status=401)

    data = read_json(request)
    if data is None:
        return JsonResponse({"errors": {"__all__": ["Geçersiz istek."]}}, status=400)

    question, options, errors = _validate_new_poll(data)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    wait = hit(POLL_CREATE, str(request.user.id))
    if wait:
        return too_many(wait)

    with transaction.atomic():
        poll = Poll.objects.create(author=request.user, question=question)
        Option.objects.bulk_create(
            [Option(poll=poll, text=text, position=index) for index, text in enumerate(options)]
        )

    return JsonResponse(serialize_poll(_poll_queryset().get(pk=poll.pk), None), status=201)


@require_http_methods(["GET", "POST"])
def poll_collection(request):
    """/api/polls/: GET lists polls, POST creates one."""
    if request.method == "POST":
        return poll_create(request)
    return poll_list(request)


@require_POST
def poll_close(request, poll_id):
    """Close a poll early. Author only; closing an already closed poll is a no-op."""
    if not request.user.is_authenticated:
        return JsonResponse({"errors": {"__all__": ["Anketi kapatmak için giriş yapmalısın."]}}, status=401)
    poll = Poll.objects.filter(pk=poll_id).first()
    if poll is None:
        return _not_found()
    if poll.author_id != request.user.id:
        return JsonResponse({"errors": {"__all__": ["Sadece kendi anketini kapatabilirsin."]}}, status=403)
    if poll.closed_at is None and not poll.is_closed:
        poll.closed_at = timezone.now()
        poll.save(update_fields=["closed_at"])
    fresh = _poll_queryset().get(pk=poll.pk)
    return JsonResponse(serialize_poll(fresh, _my_votes(request, [fresh]).get(fresh.id)))
