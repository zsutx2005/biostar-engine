import logging
from biostar.forum.models import Post, Vote, Badge

from django.utils.timezone import utc
from datetime import datetime, timedelta

logger = logging.getLogger("engine")


def now():
    return datetime.utcnow().replace(tzinfo=utc)


def wrap_list(obj, cond):
    return [obj] if cond else []


class AwardDef(object):
    def __init__(self, name, desc, func, icon, type=Badge.BRONZE):
        self.name = name
        self.desc = desc
        self.fun = func
        self.icon = icon
        self.template = ""
        self.type = type

    def validate(self, *args, **kwargs):
        try:
            value = self.fun(*args, **kwargs)
            return value
        except Exception as exc:
            logger.error("validator error %s" % exc)
        return 0

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name


# Award definitions
AUTOBIO = AwardDef(
    name="Autobiographer",
    desc="has more than 80 characters in the information field of the user's profile",
    func=lambda user: wrap_list(user, len(user.profile.text) > 80),
    icon="bullhorn icon"
)

GOOD_QUESTION = AwardDef(
    name="Good Question",
    desc="asked a question that was upvoted at least 5 times",
    func=lambda user: Post.objects.filter(vote_count__gt=5, author=user, type=Post.QUESTION),
    icon="question icon"
)

GOOD_ANSWER = AwardDef(
    name="Good Answer",
    desc="created an answer that was upvoted at least 5 times",
    func=lambda user: Post.objects.filter(vote_count__gt=5, author=user, type=Post.ANSWER),
    icon="edit outline icon"
)

STUDENT = AwardDef(
    name="Student",
    desc="asked a question with at least 3 up-votes",
    func=lambda user: Post.objects.filter(vote_count__gt=2, author=user, type=Post.QUESTION),
    icon="certificate icon"
)

TEACHER = AwardDef(
    name="Teacher",
    desc="created an answer with at least 3 up-votes",
    func=lambda user: Post.objects.filter(vote_count__gt=2, author=user, type=Post.ANSWER),
    icon="smile outline icon"
)

COMMENTATOR = AwardDef(
    name="Commentator",
    desc="created a comment with at least 3 up-votes",
    func=lambda user: Post.objects.filter(vote_count__gt=2, author=user, type=Post.COMMENT),
    icon="comment icon"
)

CENTURION = AwardDef(
    name="Centurion",
    desc="created 100 posts",
    func=lambda user: wrap_list(user, Post.objects.filter(author=user).count() > 100),
    icon="bolt icon",
    type=Badge.SILVER,
)

EPIC_QUESTION = AwardDef(
    name="Epic Question",
    desc="created a question with more than 10,000 views",
    func=lambda user: Post.objects.filter(author=user, view_count__gt=10000),
    icon="bullseye icon",
    type=Badge.GOLD,
)

POPULAR = AwardDef(
    name="Popular Question",
    desc="created a question with more than 1,000 views",
    func=lambda user: Post.objects.filter(author=user, view_count__gt=1000),
    icon="eye icon",
    type=Badge.GOLD,
)

ORACLE = AwardDef(
    name="Oracle",
    desc="created more than 1,000 posts (questions + answers + comments)",
    func=lambda user: wrap_list(user, Post.objects.filter(author=user).count() > 1000),
    icon="sun icon",
    type=Badge.GOLD,
)

PUNDIT = AwardDef(
    name="Pundit",
    desc="created a comment with more than 10 votes",
    func=lambda user: Post.objects.filter(author=user, type=Post.COMMENT, vote_count__gt=10),
    icon="comments icon",
    type=Badge.SILVER,
)

GURU = AwardDef(
    name="Guru",
    desc="received more than 100 upvotes",
    func=lambda user: wrap_list(user, Vote.objects.filter(post__author=user).count() > 100),
    icon="beer icon",
    type=Badge.SILVER,
)

CYLON = AwardDef(
    name="Cylon",
    desc="received 1,000 up votes",
    func=lambda user: wrap_list(user, Vote.objects.filter(post__author=user).count() > 1000),
    icon="rocket icon",
    type=Badge.GOLD,
)

VOTER = AwardDef(
    name="Voter",
    desc="voted more than 100 times",
    func=lambda user: wrap_list(user, Vote.objects.filter(author=user).count() > 100),
    icon="thumbs up outline"
)

SUPPORTER = AwardDef(
    name="Supporter",
    desc="voted at least 25 times",
    func=lambda user: wrap_list(user, Vote.objects.filter(author=user).count() > 25),
    icon="thumbs up icon",
    type=Badge.SILVER,
)

SCHOLAR = AwardDef(
    name="Scholar",
    desc="created an answer that has been accepted",
    func=lambda user: Post.objects.filter(author=user, type=Post.ANSWER, has_accepted=True),
    icon="check circle outline icon"
)

PROPHET = AwardDef(
    name="Prophet",
    desc="created a post with more than 20 followers",
    func=lambda user: Post.objects.filter(author=user, type__in=Post.TOP_LEVEL, subs_count__gt=20),
    icon="leaf icon"
)

LIBRARIAN = AwardDef(
    name="Librarian",
    desc="created a post with more than 10 bookmarks",
    func=lambda user: Post.objects.filter(author=user, type__in=Post.TOP_LEVEL, book_count__gt=10),
    icon="bookmark outline icon"
)


def rising_star(user):
    # The user joined no more than three months ago
    cond = now() < user.profile.date_joined + timedelta(weeks=15)
    cond = cond and Post.objects.filter(author=user).count() > 50
    return wrap_list(user, cond)

RISING_STAR = AwardDef(
    name="Rising Star",
    desc="created 50 posts within first three months of joining",
    func=rising_star,
    icon="star icon",
    type=Badge.GOLD,
)

# These awards can only be earned once
SINGLE_AWARDS = [
    AUTOBIO,
    STUDENT,
    TEACHER,
    COMMENTATOR,
    SUPPORTER,
    SCHOLAR,
    VOTER,
    CENTURION,
    CYLON,
    RISING_STAR,
    GURU,
    POPULAR,
    EPIC_QUESTION,
    ORACLE,
    PUNDIT,
    GOOD_ANSWER,
    GOOD_QUESTION,
    PROPHET,
    LIBRARIAN,
]

GREAT_QUESTION = AwardDef(
    name="Great Question",
    desc="created a question with more than 5,000 views",
    func=lambda user: Post.objects.filter(author=user, view_count__gt=5000),
    icon="fire icon",
    type=Badge.SILVER,
)

GOLD_STANDARD = AwardDef(
    name="Gold Standard",
    desc="created a post with more than 25 bookmarks",
    func=lambda user: Post.objects.filter(author=user, book_count__gt=25),
    icon="bookmark icon",
    type=Badge.GOLD,
)

APPRECIATED = AwardDef(
    name="Appreciated",
    desc="created a post with more than 5 votes",
    func=lambda user: Post.objects.filter(author=user, vote_count__gt=4),
    icon="heart icon",
    type=Badge.SILVER,
)


# These awards can be won multiple times
MULTI_AWARDS = [
    GREAT_QUESTION,
    GOLD_STANDARD,
    APPRECIATED,
]

ALL_AWARDS = SINGLE_AWARDS + MULTI_AWARDS