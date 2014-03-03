import gzip
import os


def gzip_file(fname):
    gzip_fname = fname + '.gz'
    with gzip.open(gzip_fname, 'wb') as out:
        with open(fname) as f_in:
            out.writelines(f_in)
    return gzip_fname


def gpg_encrypt(fname, recipient):
    gpg_fname = fname + '.gpg'
    cmd_words = [
        '/usr/bin/gpg',
        '--encrypt',
        '--recipient', "'{0}'".format(recipient),
        fname,
    ]
    cmd = ' '.join(cmd_words)
    os.system(cmd)
    return gpg_fname


def gpg_decrypt(fname, delete_original=False):
    gpg_fname = fname[:-4]  # removing trailing ".gpg"
    cmd_words = [
        '/usr/bin/gpg',
        '--output', "'{0}'".format(gpg_fname),
        '--decrypt',
        "'{0}'".format(fname),
    ]
    cmd = ' '.join(cmd_words)
    os.system(cmd)
    if delete_original:
        os.remove(fname)

    return gpg_fname
