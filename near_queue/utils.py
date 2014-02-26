import gzip
import os


def gzip_file(fname, delete_original=False):
    gzip_fname = fname + '.gz'
    with gzip.open(gzip_fname, 'wb') as out:
        with open(fname) as f_in:
            out.writelines(f_in)
    if delete_original:
        os.remove(fname)

    return gzip_fname


def gpg_encrypt(fname, recipient, delete_original=False):
    gpg_fname = fname + '.gpg'
    cmd_words = [
        'gpg',
        '--encrypt',
        '--recipient', "'{0}'".format(recipient),
        fname,
    ]
    cmd = ' '.join(cmd_words)
    os.system(cmd)
    if delete_original:
        os.remove(fname)

    return gpg_fname


def gpg_decrypt(fname, delete_original=False):
    gpg_fname = fname[:-4]  # removing trailing ".gpg"
    cmd_words = [
        'gpg',
        '--output', "'{0}'".format(gpg_fname),
        '--decrypt',
        "'{0}'".format(fname),
    ]
    cmd = ' '.join(cmd_words)
    os.system(cmd)
    if delete_original:
        os.remove(fname)

    return gpg_fname
