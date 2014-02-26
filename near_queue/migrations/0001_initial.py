# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Queue'
        db.create_table(u'near_queue_queue', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal(u'near_queue', ['Queue'])

        # Adding unique constraint on 'Queue', fields ['name']
        db.create_unique(u'near_queue_queue', ['name'])

        # Adding model 'QueueEntry'
        db.create_table(u'near_queue_queueentry', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('queue', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['near_queue.Queue'])),
            ('sort_key', self.gf('django.db.models.fields.CharField')(max_length=256, null=True, blank=True)),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('is_complete', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('time_completed', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('time_added', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal(u'near_queue', ['QueueEntry'])

        # Adding unique constraint on 'QueueEntry', fields ['queue', 'key']
        db.create_unique(u'near_queue_queueentry', ['queue_id', 'key'])


    def backwards(self, orm):
        # Removing unique constraint on 'QueueEntry', fields ['queue', 'key']
        db.delete_unique(u'near_queue_queueentry', ['queue_id', 'key'])

        # Removing unique constraint on 'Queue', fields ['name']
        db.delete_unique(u'near_queue_queue', ['name'])

        # Deleting model 'Queue'
        db.delete_table(u'near_queue_queue')

        # Deleting model 'QueueEntry'
        db.delete_table(u'near_queue_queueentry')


    models = {
        u'near_queue.queue': {
            'Meta': {'unique_together': "(('name',),)", 'object_name': 'Queue'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        u'near_queue.queueentry': {
            'Meta': {'ordering': "('queue', 'sort_key', 'time_added', 'key')", 'unique_together': "(('queue', 'key'),)", 'object_name': 'QueueEntry'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_complete': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'queue': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['near_queue.Queue']"}),
            'sort_key': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'time_added': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'time_completed': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['near_queue']