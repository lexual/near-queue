import abc
import logging
import os
import re
import rowdy.sftp

from contextlib import contextmanager
from tempfile import mkstemp

from boto.s3.connection import S3Connection
from boto.s3.key import Key

from near_queue.models import Queue
from near_queue.models import QueueEntry
from near_queue.utils import gzip_file
from near_queue.utils import gpg_decrypt
from near_queue.utils import gpg_encrypt


logger = logging.getLogger(__name__.split('.')[0])


@contextmanager
def log_before_and_after(msg):
    logger.info('(running) ' + msg + ' ...')
    yield
    logger.info('(complete) ' + msg)




class Processor(object):
    """Base class"""

    __metaclass__ = abc.ABCMeta

    @classmethod
    def process_queued_files(cls):
        process_s3_files(queue_name=cls.S3_PROCESS_QUEUE,
                         s3_account=cls.S3_ACCOUNT,
                         processor_fn=cls.processor,
                         decrypt=cls.ENCRYPT_FILE)

    @staticmethod
    def processor(localpath):
        raise NotImplemented


class SFTP_S3_CSV_Processor(Processor):
    """
    Put files from sftp onto s3, and process them.

    Class variables to set.
    S3_UPLOAD_QUEUE = 'X'
    S3_PROCESS_QUEUE = 'X'
    S3_DIRECTORY = 'X'
    S3_ACCOUNT = S3Account(...)
    SFTP_ACCOUNT = SFTPAccount(...)
    SFTP_FOLDER = 'X'
    SFTP_FILE_REGEX = 'X'
    COMPRESS_FILE = bool
    #REMOVE_FROM_SFTP = settings.DELETE_SFTP_AFTER_S3_UPLOAD
    """

    __metaclass__ = abc.ABCMeta

    @classmethod
    def retrieve_and_process_files(cls):
        """
        Looks for csvs on sftp, processes them, saves into sql table.
        """
        cls.enqueue_files_for_s3_uploading()
        cls.put_files_on_s3()
        cls.process_queued_files()

    @classmethod
    def enqueue_files_for_s3_uploading(cls):
        enqueue_sftp_files(queue_name=cls.S3_UPLOAD_QUEUE,
                           sftp_account=cls.SFTP_ACCOUNT,
                           sftp_folder=cls.SFTP_FOLDER,
                           file_regex=cls.SFTP_FILE_REGEX)

    @classmethod
    def put_files_on_s3(cls):
        if cls.ENCRYPT_FILE:
            gpg_recipient = cls.ENCRYPT_RECIPIENT
        else:
            gpg_recipient = None
        send_sftp_files_into_s3(sftp_queue=cls.S3_UPLOAD_QUEUE,
                                s3_queue=cls.S3_PROCESS_QUEUE,
                                sftp_account=cls.SFTP_ACCOUNT,
                                s3_account=cls.S3_ACCOUNT,
                                s3_directory=cls.S3_DIRECTORY,
                                remove_from_sftp=cls.REMOVE_FROM_SFTP,
                                compress=cls.COMPRESS_FILE,
                                gpg_recipient=gpg_recipient)


def enqueue_sftp_files(queue_name, sftp_account, sftp_folder, file_regex):
    q, _ = Queue.objects.get_or_create(name=queue_name)
    sftp = rowdy.sftp.SFTPConnection(sftp_account.username,
                                     sftp_account.password,
                                     sftp_account.hostname)
    sftp.open_connection()
    files = sftp.listdir(sftp_folder)
    files = [os.path.join(sftp_folder, f) for f in files]
    files = [f for f in files if re.match(file_regex, f)]
    for f in files:
        qe, created = QueueEntry.objects.get_or_create(queue=q,
                                                       key=f)
        if created:
            logger.info('sftp file queued: {0}'.format(qe))
        else:
            logger.info('already in queue: {0}'.format(qe))
    sftp.close_connection()


def send_sftp_files_into_s3(sftp_queue, s3_queue, sftp_account, s3_account,
                            s3_directory, remove_from_sftp=False,
                            compress=True, gpg_recipient=None):
    upload_q, _ = Queue.objects.get_or_create(name=sftp_queue)
    entries = QueueEntry.objects.filter(queue=upload_q, is_complete=False)
    process_q, _ = Queue.objects.get_or_create(name=s3_queue)
    for entry in entries:
        with log_before_and_after('handling: {0}'.format(entry)):
            s3_key = _put_sftp_file_on_s3(entry.key, s3_account, s3_directory,
                                          sftp_account,
                                          remove_from_sftp=remove_from_sftp,
                                          compress=compress,
                                          gpg_recipient=gpg_recipient)
            qe, _ = QueueEntry.objects.get_or_create(queue=process_q,
                                                     key=s3_key,
                                                     sort_key=s3_key)
            qe.is_complete = False
            qe.save()
            entry.mark_as_complete()


def _put_sftp_file_on_s3(fname, s3_account, s3_directory, sftp_account,
                         remove_from_sftp=False, compress=True,
                         gpg_recipient=None):
    sftp = rowdy.sftp.SFTPConnection(sftp_account.username,
                                     sftp_account.password,
                                     sftp_account.hostname)
    _, tempfile = mkstemp()
    sftp.open_connection()
    sftp.get(fname, tempfile)
    sftp.close_connection()

    s3_key = os.path.join(s3_directory, os.path.basename(fname))
    if compress:
        s3_key += '.gz'
        tempfile = gzip_file(tempfile, delete_original=True)
    if gpg_recipient is not None:
        s3_key += '.gpg'
        tempfile = gpg_encrypt(tempfile, gpg_recipient, delete_original=True)

    conn = S3Connection(aws_access_key_id=s3_account.access_key,
                        aws_secret_access_key=s3_account.secret_key,
                        host=s3_account.host)
    bucket = conn.get_bucket(s3_account.bucket)
    k = Key(bucket, name=s3_key)
    k.set_contents_from_filename(tempfile)
    os.remove(tempfile)

    if remove_from_sftp:
        sftp.open_connection()
        sftp.remove(fname)
        sftp.close_connection()

    return s3_key


def process_s3_files(queue_name, s3_account, processor_fn, decrypt):
    q, _ = Queue.objects.get_or_create(name=queue_name)
    entries = QueueEntry.objects.filter(queue=q, is_complete=False)
    with log_before_and_after('handling: {0}'.format(queue_name)):
        for entry in entries:
            with log_before_and_after('handling: {0}'.format(entry)):
                base = os.path.basename(entry.key)
                _, tmp_fname = mkstemp(suffix=base)

                conn = S3Connection(aws_access_key_id=s3_account.access_key,
                                    aws_secret_access_key=s3_account.secret_key,
                                    host=s3_account.host)
                bucket = conn.get_bucket(s3_account.bucket)

                k = Key(bucket, name=entry.key)
                k.get_contents_to_filename(tmp_fname)

                tmp_fname = gpg_decrypt(tmp_fname, delete_original=True)
                processor_fn(tmp_fname)

                os.remove(tmp_fname)
                entry.mark_as_complete()


class IMAP_S3_CSV_Processor(Processor):
    """
    Process files from IMAP into S3

    Class variables to specify.
    S3_UPLOAD_QUEUE = 'X'
    S3_PROCESS_QUEUE = 'X'
    IMAP_MBOX = 'X'
    IMAP_FILE_REGEX = 'X'
    IMAP_ACCOUNT = IMAPConnection(...)
    S3_DIRECTORY = 'X'
    S3_ACCOUNT = S3Account(...)
    COMPRESS_FILE = True/False
    ENCRYPT_FILE = True/False
    ENCRYPT_RECIPIENT = settings.GPG_NAME
    #IMAP_ARCHIVE_MBOX = None
    #IMAP_ARCHIVE_MBOX = '[Gmail]/Trash'
    """

    __metaclass__ = abc.ABCMeta

    @classmethod
    def retrieve_and_process_files(cls):
        """
        Looks for attachments on imap, processes them, saves into sql table.
        """
        cls.enqueue_emails_for_s3_uploading()
        cls.put_attachments_on_s3()
        cls.process_queued_files()

    @classmethod
    def enqueue_emails_for_s3_uploading(cls):
        enqueue_imap_emails(queue_name=cls.S3_UPLOAD_QUEUE,
                            imap_account=cls.IMAP_ACCOUNT,
                            mailbox=cls.IMAP_MBOX,
                            file_regex=cls.IMAP_FILE_REGEX)

    @classmethod
    def put_attachments_on_s3(cls):
        if cls.ENCRYPT_FILE:
            gpg_recipient = cls.ENCRYPT_RECIPIENT
        else:
            gpg_recipient = None
        send_imap_attachments_into_s3(imap_queue=cls.S3_UPLOAD_QUEUE,
                                      s3_queue=cls.S3_PROCESS_QUEUE,
                                      imap_account=cls.IMAP_ACCOUNT,
                                      file_regex=cls.IMAP_FILE_REGEX,
                                      s3_account=cls.S3_ACCOUNT,
                                      s3_directory=cls.S3_DIRECTORY,
                                      imap_archive_mbox=cls.IMAP_ARCHIVE_MBOX,
                                      compress=cls.COMPRESS_FILE,
                                      gpg_recipient=gpg_recipient)


def enqueue_imap_emails(queue_name, imap_account, mailbox, file_regex):
    """Queue each email in mailbox for their attachments to be uploaded"""
    q, _ = Queue.objects.get_or_create(name=queue_name)
    imap_account.open_connection()
    uid_validity = imap_account.uid_validity(mailbox)
    uids = imap_account.list_uids(mailbox)
    for uid in uids:
        imap_relative_url = '{0};UID={1}/;UIDVALIDITY={2}'.format(mailbox,
                                                                  uid,
                                                                  uid_validity)
        qe, created = QueueEntry.objects.get_or_create(queue=q,
                                                       key=imap_relative_url)
        if created:
            logger.info('imap email queued: {0}'.format(qe))
        else:
            logger.info('already in queue: {0}'.format(qe))
    imap_account.close_connection()


def send_imap_attachments_into_s3(imap_queue, s3_queue, imap_account,
                                  file_regex,
                                  s3_account, s3_directory,
                                  imap_archive_mbox=None, compress=True,
                                  gpg_recipient=None):
    """For each email, upload matching attachments into s3"""
    upload_q, _ = Queue.objects.get_or_create(name=imap_queue)
    entries = QueueEntry.objects.filter(queue=upload_q, is_complete=False)
    process_q, _ = Queue.objects.get_or_create(name=s3_queue)
    for entry in entries:
        with log_before_and_after('handling: {0}'.format(entry)):
            s3_keys = _put_imap_attachments_on_s3(entry.key, s3_account,
                                                  s3_directory,
                                                  imap_account,
                                                  file_regex,
                                                  imap_archive_mbox,
                                                  compress=compress,
                                                  gpg_recipient=gpg_recipient)
            for s3_key in s3_keys:
                qe, _ = QueueEntry.objects.get_or_create(queue=process_q,
                                                         key=s3_key,
                                                         sort_key=s3_key)
                qe.is_complete = False
                qe.save()
                entry.mark_as_complete()


def _put_imap_attachments_on_s3(imap_url, s3_account, s3_directory,
                                imap_account, file_regex,
                                imap_archive_mbox=None, compress=True,
                                gpg_recipient=None):
    imap_details = parse_imap_url(imap_url)
    imap_account.open_connection()
    attachmnts = imap_account.download_attachments(imap_details['mailbox'],
                                                   imap_details['UID'],
                                                   imap_details['UIDVALIDITY'],
                                                   filename_regex=file_regex)
    imap_account.close_connection()
    conn = S3Connection(aws_access_key_id=s3_account.access_key,
                        aws_secret_access_key=s3_account.secret_key,
                        host=s3_account.host)
    bucket = conn.get_bucket(s3_account.bucket)
    s3_keys = []
    for attach in attachmnts:
        remote_key = '{0}_{1}'.format(attach['utc_date'].isoformat(),
                                      attach['remote_fname'])
        s3_key = os.path.join(s3_directory, remote_key)
        if compress:
            s3_key += '.gz'
            attach['local_fname'] = gzip_file(attach['local_fname'],
                                              delete_original=True)
        if gpg_recipient is not None:
            s3_key += '.gpg'
            attach['local_fname'] = gpg_encrypt(attach['local_fname'],
                                                gpg_recipient,
                                                delete_original=True)
        k = Key(bucket, name=s3_key)
        k.set_contents_from_filename(attach['local_fname'])
        os.remove(attach['local_fname'])
        s3_keys.append(s3_key)
    if imap_archive_mbox:
        imap_account.open_connection()
        imap_account.move(imap_details['mailbox'],
                          imap_details['UID'],
                          imap_details['UIDVALIDITY'],
                          imap_archive_mbox)
        imap_account.close_connection()
    return s3_keys


def parse_imap_url(url):
    """Currently only supporting relative urls like:
    adlens_archive;UID=193/;UIDVALIDITY=19
    """
    parts = url.split(';')
    parts = [part.rstrip('/') for part in parts]
    result = {}
    result['mailbox'] = parts[0]
    for part in parts[1:]:
        k, v = part.split('=')
        result[k] = int(v)
    return result
