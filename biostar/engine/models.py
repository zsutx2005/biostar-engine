import logging

import hjson
import mistune
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template import loader
from django.urls import reverse
from django.utils import timezone

from django.conf import settings
from biostar.accounts.models import User
from . import util
from .const import *

logger = logging.getLogger("engine")


def join(*args):
    return os.path.abspath(os.path.join(*args))


class Bunch(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def get_placeholder():
    return os.path.dirname(join(settings.STATIC_ROOT, 'images', 'placeholder.png'))


def make_html(text):
    html = mistune.markdown(text, escape=False)
    return html


def image_path(instance, filename):
    # Name the data by the filename.
    name, ext = os.path.splitext(filename)

    uid = util.get_uuid(6)
    dirpath = instance.get_project_dir()
    imgname = f"images/image-{uid}{ext}"

    # Uploads need to go relative to media directory.
    path = os.path.relpath(dirpath, settings.MEDIA_ROOT)

    imgpath = os.path.join(path, imgname)

    return imgpath


class Manager(models.Manager):

    def get_queryset(self):
        "Regular queries exclude deleted stuff"
        return super().get_queryset().filter(deleted=False).select_related("owner", "owner__profile", "lastedit_user",
                                                                           "lastedit_user__profile")

    def get_deleted(self, **kwargs):
        "Only show deleted things"
        return super().get_queryset().filter(deleted=True, **kwargs).select_related("owner", "owner__profile",
                                                                                    "lastedit_user",
                                                                                    "lastedit_user__profile")

    def get_all(self, **kwargs):
        "Return everything"
        return super().get_queryset().filter(**kwargs).select_related("owner", "owner__profile", "lastedit_user",
                                                                      "lastedit_user__profile")


class Project(models.Model):
    PUBLIC, SHAREABLE, PRIVATE = 1, 2, 3
    PRIVACY_CHOICES = [(PRIVATE, "Private"), (SHAREABLE, "Shareable Link"), (PUBLIC, "Public")]

    # Rank in a project list.
    rank = models.FloatField(default=100)

    # The user that edited the object most recently.
    lastedit_user = models.ForeignKey(User, related_name='proj_editor', null=True, on_delete=models.CASCADE)
    lastedit_date = models.DateTimeField(default=timezone.now)

    # Limits who can access the project.
    privacy = models.IntegerField(default=PRIVATE, choices=PRIVACY_CHOICES)
    image = models.ImageField(default=None, blank=True, upload_to=image_path, max_length=MAX_FIELD_LEN)
    name = models.CharField(default="New Project", max_length=MAX_NAME_LEN)
    deleted = models.BooleanField(default=False)

    # We need to keep the owner.
    owner = models.ForeignKey(User, null=False, on_delete=models.CASCADE)
    text = models.TextField(default='Project description.', max_length=MAX_TEXT_LEN)

    html = models.TextField(default='html', max_length=MAX_LOG_LEN)
    date = models.DateTimeField(auto_now_add=True)
    uid = models.CharField(max_length=32, unique=True)

    objects = Manager()

    def save(self, *args, **kwargs):
        now = timezone.now()
        self.date = self.date or now
        self.html = make_html(self.text)
        self.name = self.name[:MAX_NAME_LEN]
        self.uid = self.uid or util.get_uuid(8)
        self.lastedit_user = self.lastedit_user or self.owner
        self.lastedit_date = now

        if not os.path.isdir(self.get_project_dir()):
            os.makedirs(self.get_project_dir())

        super(Project, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

    def uid_is_set(self):
        assert bool(self.uid.strip()), "Sanity check. UID should always be set."

    def url(self):
        self.uid_is_set()
        return reverse("project_view", kwargs=dict(uid=self.uid))

    def get_project_dir(self):
        self.uid_is_set()
        return join(settings.MEDIA_ROOT, "projects", f"{self.uid}")

    def get_data_dir(self):
        "Match consistency of data dir calls"
        return self.get_project_dir()

    @property
    def is_public(self):
        return self.privacy == self.PUBLIC

    @property
    def is_private(self):
        return self.privacy == self.PRIVATE

    @property
    def project(self):
        return self

    @property
    def json_text(self):
        return hjson.dumps(self.json_data)

    @property
    def json_data(self):
        payload = dict(
            settings=dict(
                uid=self.uid,
                name=self.name,
                image=f"{'_'.join(self.name.split())}-{self.pk}.png",
                privacy=dict(self.PRIVACY_CHOICES)[self.privacy],
                help=self.text,
                url=settings.BASE_URL,
                project_uid=self.uid,
                id=self.pk
                ),
            recipes=[recipe.uid for recipe in self.analysis_set.all()])

        return payload

    @property
    def summary(self):
        """
        Returns first line of text
        """
        lines = self.text.splitlines() or ['']
        first = lines[0]
        return first


class Access(models.Model):
    """
    Allows access of users to Projects.
    """
    NO_ACCESS, READ_ACCESS, WRITE_ACCESS, = 1, 2, 3
    ACCESS_CHOICES = [
        (NO_ACCESS, "No Access"),
        (READ_ACCESS, "Read Access"),
        (WRITE_ACCESS, "Write Access"),
    ]

    ACCESS_MAP = dict(ACCESS_CHOICES)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    access = models.IntegerField(default=NO_ACCESS, choices=ACCESS_CHOICES, db_index=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} on {self.project.name}"

    def save(self, *args, **kwargs):
        super(Access, self).save(*args, **kwargs)


@receiver(post_save, sender=Project)
def update_access(sender, instance, created, raw, update_fields, **kwargs):
    # Give the owner WRITE ACCESS if they do not have it.
    entry = Access.objects.filter(user=instance.owner, project=instance, access=Access.WRITE_ACCESS)
    if entry.first() is None:
        entry = Access.objects.create(user=instance.owner, project=instance, access=Access.WRITE_ACCESS)


class Data(models.Model):
    PENDING, READY, ERROR, = 1, 2, 3
    STATE_CHOICES = [(PENDING, "Pending"), (READY, "Ready"), (ERROR, "Error")]
    state = models.IntegerField(default=PENDING, choices=STATE_CHOICES)

    LINK, UPLOAD, TEXTAREA = 1, 2, 3
    METHOD_CHOICE = [(LINK, "Linked Data"), (UPLOAD, "Uploaded Data"), (TEXTAREA, "Text Field")]
    method = models.IntegerField(default=LINK, choices=METHOD_CHOICE)

    name = models.CharField(max_length=MAX_NAME_LEN, default="My Data")
    image = models.ImageField(default=None, blank=True, upload_to=image_path, max_length=MAX_FIELD_LEN)

    deleted = models.BooleanField(default=False)

    # Rank on a data list.
    rank = models.FloatField(default=100)

    # The user that edited the object most recently.
    lastedit_user = models.ForeignKey(User, related_name='data_editor', null=True, on_delete=models.CASCADE)
    lastedit_date = models.DateTimeField(default=timezone.now)

    owner = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    text = models.TextField(default='Data description.', max_length=MAX_TEXT_LEN, blank=True)
    html = models.TextField(default='html')
    date = models.DateTimeField(auto_now_add=True)

    type = models.CharField(max_length=MAX_NAME_LEN, default="DATA")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    size = models.BigIntegerField(default=0)

    # FilePathField points to an existing file
    file = models.FilePathField(max_length=MAX_FIELD_LEN, path=get_placeholder())

    uid = models.CharField(max_length=32, unique=True)

    objects = Manager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        now = timezone.now()
        self.name = self.name[-MAX_NAME_LEN:]
        self.uid = self.uid or util.get_uuid(8)
        self.date = self.date or now
        self.html = make_html(self.text)
        self.owner = self.owner or self.project.owner
        self.type = self.type.replace(" ", '')
        self.lastedit_user = self.lastedit_user or self.owner or self.project.owner
        self.lastedit_date = now

        # Build the data directory.
        data_dir = self.get_data_dir()
        if not os.path.isdir(data_dir):
            os.makedirs(data_dir)

        # Set the table of contents for the file.
        self.file = self.get_path()

        # Make this file if it does not exist
        if not os.path.isfile(self.file):
            with open(self.file, 'wt') as fp:
                pass

        super(Data, self).save(*args, **kwargs)

    def peek(self):
        """
        Returns a preview of the data
        """
        try:
            target = self.get_path()
            lines = open(target, 'rt').readlines()
            if len(lines) == 1:
                target = lines[0]
                return util.smart_preview(target)
            else:
                data_dir = self.get_data_dir()
                rels = [os.path.relpath(path, data_dir) for path in lines]
                return "".join(rels)
        except Exception as exc:
            return f"Error :{exc}"

    def __str__(self):
        return self.name

    def get_data_dir(self):
        "The data directory"
        assert self.uid, "Sanity check. UID should always be set."
        return join(self.get_project_dir(), f"{self.uid}")

    def get_project_dir(self):
        return self.project.get_project_dir()

    def get_path(self):
        path = join(settings.TOC_ROOT, f"toc-{self.uid}.txt")
        return path

    def make_toc(self):

        tocname = self.get_path()

        collect = util.findfiles(self.get_data_dir(), collect=[])

        # Create a sorted file path collection.
        collect.sort()
        # Write the table of contents.
        with open(tocname, 'w') as fp:
            fp.write("\n".join(collect))

        # Find the cumulative size of the files.
        size = 0
        for elem in collect:
            if os.path.isfile(elem):
                size += os.stat(elem, follow_symlinks=True).st_size

        self.size = size
        self.file = tocname

        return tocname

    def can_unpack(self):
        cond = str(self.get_path()).endswith("tar.gz")
        return cond

    def get_files(self):
        fnames = [line.strip() for line in open(self.get_path(), 'rt')]
        return fnames if len(fnames) else [""]

    def get_url(self, path=""):
        "Returns url to the data directory"
        return f"projects/{self.project.uid}/{self.uid}/" + path

    def url(self):
        return reverse('data_view', kwargs=dict(uid=self.uid))

    def fill_dict(self, obj):
        """
        Mutates a dictionary object to fill in more fields based
        on the current object.
        """
        fnames = self.get_files()
        if fnames:
            obj['value'] = fnames[0]
        else:
            obj['value'] = 'MISSING'

        obj['files'] = fnames
        obj['toc'] = self.get_path()
        obj['id'] = self.id
        obj['name'] = self.name
        obj['uid'] = self.uid
        obj['data_dir'] = self.get_data_dir()
        obj['project_dir'] = self.get_project_dir()
        obj['data_url'] = self.url()

    @property
    def summary(self):
        """
        Returns first line of text
        """
        lines = self.text.splitlines() or ['']
        first = lines[0]
        return first


class Analysis(models.Model):
    AUTHORIZED, UNDER_REVIEW = 1, 2

    AUTH_CHOICES = [(AUTHORIZED, "All users may run recipe"), (UNDER_REVIEW, "Only moderators may run recipe")]

    security = models.IntegerField(default=UNDER_REVIEW, choices=AUTH_CHOICES)

    deleted = models.BooleanField(default=False)
    uid = models.CharField(max_length=32, unique=True)

    name = models.CharField(max_length=MAX_NAME_LEN, default="My Recipe")
    text = models.TextField(default='This is the recipe description.', max_length=MAX_TEXT_LEN)
    html = models.TextField(default='html')
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    # The rank in a recipe list.
    rank = models.FloatField(default=100)

    # The user that edited the object most recently.
    lastedit_user = models.ForeignKey(User, related_name='analysis_editor', null=True, on_delete=models.CASCADE)
    lastedit_date = models.DateTimeField(default=timezone.now)

    diff_author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="diff_author", null=True)
    diff_date = models.DateField(blank=True, auto_now_add=True)

    project = models.ForeignKey(Project, on_delete=models.CASCADE)

    json_text = models.TextField(default="{}", max_length=MAX_TEXT_LEN)
    template = models.TextField(default="")
    last_valid = models.TextField(default='')

    date = models.DateTimeField(auto_now_add=True, blank=True)
    image = models.ImageField(default=None, blank=True, upload_to=image_path, max_length=MAX_FIELD_LEN,
                              help_text="Optional image")

    objects = Manager()

    def __str__(self):
        return self.name

    @property
    def json_data(self):
        """
        Returns the json_text as parsed json_data
        """
        json_data = hjson.loads(self.json_text)

        # Generates file names
        base = f"{'_'.join(self.name.split())}_{self.project.uid}_{self.pk}"
        template_name = f"{base}.sh"
        image_name = f"{base}.png"

        # Previously set values.
        current_settings = json_data.get("settings") or {}

        # Overwrite any previously set values with current information.
        current_settings["name"] = self.name
        current_settings["template"] = template_name
        current_settings["image"] = image_name
        current_settings["id"] = self.pk
        current_settings["recipe_uid"] = self.uid
        current_settings["uid"] = self.uid
        current_settings["help"] = self.text
        current_settings["url"] = settings.BASE_URL

        # Put them back into settings.
        json_data["settings"] = current_settings

        return json_data

    def save(self, *args, **kwargs):
        now = timezone.now()
        self.uid = self.uid or util.get_uuid(8)
        self.date = self.date or now
        self.diff_date = self.diff_date or now
        self.text = self.text or "Recipe description"
        self.name = self.name[:MAX_NAME_LEN] or "New Recipe"
        self.html = make_html(self.text)
        self.diff_author = self.diff_author or self.owner
        self.lastedit_user = self.lastedit_user or self.owner or self.project.owner
        self.lastedit_date = now

        # Ensure Unix line endings.
        self.template = self.template.replace('\r\n', '\n') if self.template else ""

        if self.security == self.AUTHORIZED:
            self.last_valid = self.template

        super(Analysis, self).save(*args, **kwargs)

    def get_project_dir(self):
        return self.project.get_project_dir()

    def url(self):
        assert self.uid, "Sanity check. UID should always be set."
        return reverse("recipe_view", kwargs=dict(uid=self.uid))

    def runnable(self):
        return self.security == self.AUTHORIZED

    @property
    def running_css(self):
        "css display for running and not running jobs"
        return "runnable" if self.security == self.AUTHORIZED else "not_runnable"

    @property
    def summary(self):
        """
        Returns first line of text
        """
        lines = self.text.splitlines() or ['']
        first = lines[0]
        return first


@receiver(post_save, sender=Analysis)
def sync_json(sender, instance, created, raw, update_fields, **kwargs):
    # Sync the json["settings"] with the recipe.text and name.

    current_json = instance.json_data

    data = current_json.get("settings") or {}

    data["name"] = instance.name
    data["help"] = instance.text

    current_json["settings"] = data

    Analysis.objects.get_all(uid=instance.uid).update(json_text=hjson.dumps(current_json))


class Job(models.Model):
    AUTHORIZED, UNDER_REVIEW = 1, 2
    AUTH_CHOICES = [(AUTHORIZED, "Authorized"), (UNDER_REVIEW, "Authorization Required")]

    QUEUED, RUNNING, COMPLETED, ERROR, SPOOLED, PAUSED = range(1, 7)

    STATE_CHOICES = [(QUEUED, "Queued"), (RUNNING, "Running"), (PAUSED, "Paused"),
                     (SPOOLED, "Spooled"), (COMPLETED, "Completed"), (ERROR, "Error")]

    state = models.IntegerField(default=QUEUED, choices=STATE_CHOICES)

    deleted = models.BooleanField(default=False)
    name = models.CharField(max_length=MAX_NAME_LEN, default="New results")
    image = models.ImageField(default=None, blank=True, upload_to=image_path, max_length=MAX_FIELD_LEN)

    # The user that edited the object most recently.
    lastedit_user = models.ForeignKey(User, related_name='job_editor', null=True, on_delete=models.CASCADE)
    lastedit_date = models.DateTimeField(default=timezone.now)

    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(default='Result description.', max_length=MAX_TEXT_LEN)
    html = models.TextField(default='html')

    # Job creation date
    date = models.DateTimeField(auto_now_add=True)

    # Job runtime date.
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    json_text = models.TextField(default="commands")

    uid = models.CharField(max_length=32)
    template = models.TextField(default="makefile")

    # Set the security level.
    security = models.IntegerField(default=UNDER_REVIEW, choices=AUTH_CHOICES)

    # This will be set when the job attempts to run.
    script = models.TextField(default="")

    # Keeps track of errors.
    stdout_log = models.TextField(default="", max_length=MAX_LOG_LEN)

    # Standard error.
    stderr_log = models.TextField(default="", max_length=MAX_LOG_LEN)

    # Will be false if the objects is to be deleted.
    valid = models.BooleanField(default=True)

    path = models.FilePathField(default="")

    objects = Manager()

    def is_running(self):
        return self.state == Job.RUNNING

    def __str__(self):
        return self.name

    def get_url(self, path=''):
        """
        Return the url to the job directory
        """
        return f"jobs/{self.uid}/" + path

    def url(self):
        return reverse("job_view", kwargs=dict(uid=self.uid))

    def get_project_dir(self):
        return self.project.get_project_dir()

    def get_data_dir(self):
        # TODO: MIGRATION FIX - needs refactoring
        path = join(settings.MEDIA_ROOT, "jobs", self.uid)
        return path

    @property
    def json_data(self):
        "Returns the json_text as parsed json_data"
        return hjson.loads(self.json_text)

    def elapsed(self):
        if not (self.start_date and self.end_date):
            value = ''
        else:
            seconds = int((self.end_date - self.start_date).seconds)
            if seconds < 60:
                value = f'{seconds} seconds'
            elif seconds < 3600:
                minutes = int(seconds / 60)
                value = f'{minutes} minutes'
            else:
                hours = round(seconds / 3600, 1)
                value = f'{hours} hours'

        return value

    def done(self):
        return self.state == Job.COMPLETED

    def make_path(self):
        path = join(settings.MEDIA_ROOT, "jobs", f"{self.uid}")
        return path

    def save(self, *args, **kwargs):
        now = timezone.now()
        self.name = self.name or f"Results for: {self.analysis.name}"
        self.date = self.date or now
        self.html = make_html(self.text)
        self.name = self.name[:MAX_NAME_LEN]
        self.uid = self.uid or util.get_uuid(8)
        self.template = self.analysis.template
        self.stderr_log = self.stderr_log[:MAX_LOG_LEN]
        self.stdout_log = self.stdout_log[:MAX_LOG_LEN]
        self.name = self.name or self.analysis.name
        self.path = self.make_path()
        self.lastedit_user = self.lastedit_user or self.owner or self.project.owner
        self.lastedit_date = now

        if not os.path.isdir(self.path):
            os.makedirs(self.path)

        super(Job, self).save(*args, **kwargs)

    @property
    def summary(self):
        """
        Creates informative job summary that shows job parameters.
        """
        summary_template = "widgets/job_summary.html"
        context = dict(data=self.json_data)
        template = loader.get_template(summary_template)
        result = template.render(context)

        return result
