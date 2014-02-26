import datetime
from django.db import models


class Queue(models.Model):
    name = models.CharField(max_length=64)

    def __unicode__(self):
        return self.name

    class Meta:
        unique_together = ('name',)


class QueueEntry(models.Model):
    """
    Simple queue for handling files to be processed.

    Refer to different queue's by specifying queue.
    """
    queue = models.ForeignKey(Queue)

    sort_key = models.CharField(max_length=256, null=True, blank=True)
    key = models.CharField(max_length=256)
    is_complete = models.BooleanField(default=False)
    time_completed = models.DateTimeField(null=True, blank=True)

    time_added = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return '{0}: {1} - {2}'.format(self.queue, self.key, self.is_complete)

    def mark_as_complete(self):
        self.is_complete = True
        self.time_completed = datetime.datetime.utcnow()
        self.save()

    class Meta:
        unique_together = ('queue', 'key')
        ordering = ('queue', 'sort_key', 'time_added', 'key')
