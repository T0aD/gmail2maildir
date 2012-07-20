#! /usr/bin/python

# Oh putaing: https://developers.google.com/google-apps/gmail/imap_extensions

# Basically Gmail provides us with an unique ID per mail so we know what emails not to duplicate
# Then on Gmail, the uidvalidity is the unique ID that will never change of a directory
# (contrary to for instance my vpopmail / dovecot setup where uidvalidity is just the timestamp
# of the mailbox directory and then cannot be trusted to check if a mailbox was renamed)
import mailbox
import imaplib
import re
import os
import sqlite3

##
# Configuration

# Short version:
#username, password = 'your email', 'your password'

if not 'username' in locals() or not 'password' in locals():
    if os.path.exists('.account'):
        fd = open('.account')
        data = fd.readline()
        fd.close()
        username, password = data.rstrip('\n').split('::')
    else:
        print "You should create a file .account with the following format:"
        print "your email::your password"
        exit(1)

# cause fucking imaplib apparently sucks (with python3x) // Not used
"""
#imap_target, port = imaplib.IMAP4, 143
imap_target, port = imaplib.IMAP4_SSL, 993
class IMAP4FIX(imap_target):
    def _CRAM_MD5_AUTH(self, challenge):
        import hmac
        login = self.user + " " + hmac.HMAC(self.password.encode(), challenge).hexdigest()       
        return login
#imap = IMAP4FIX(hostname, port)
"""


##
# Grabs folders and emails from GMAIL:
class Gmail:
    def __init__(self, username=False, password=False, ssl=True, port=False, hostname=False):

        # List of folders to skip
        self.skip = ['[Gmail]/Drafts', '[Gmail]/Important', 
                     '[Gmail]/Spam', '[Gmail]/Trash', '[Gmail]/Starred']
        self.re_size = re.compile(r'\d+ \(RFC822 {(\d+)}')

        # Parse parameters
        if hostname is False:
            self.hostname = 'imap.gmail.com'
        self.username = username
        self.password = password
        self.ssl = ssl
        if port is False:
            if ssl is True:
                self.port = 993
            else:
                self.port = 143
        self.login()

    def login(self):
        if self.ssl is True:
            target = imaplib.IMAP4_SSL
        else:
            target = imaplib.IMAP4
        self.imap = target(self.hostname, self.port)
        self.imap.login(self.username, self.password)
        print '[i] connected with %s on %s:%d' % (self.username, self.hostname, self.port)

    def logout(self):
        self.imap.logout()

    def get_folders(self):
        reg = re.compile(r'^\(([^)]+)\) "[/\.]" "(.*)"$')
        reguid = re.compile(r'\(UIDVALIDITY (\d+)\)$')
        rv, data = self.imap.list()
        if rv != 'OK':
            raise Exception("Couldnt fetch folders")
        folders = {}
        for folder in data:
            m = reg.search(folder)
            if m:
                name = m.group(2)
                if not name in self.skip:
                    typ, data = self.imap.status(name, '(UIDVALIDITY)')
                    if typ != 'OK':
                        continue
                    m = reguid.search(data[0])
                    if m:
                        uid = int(m.group(1))
                        folders[uid] = name
        return folders

    def get_mails(self, folder, fuid):
        reg = re.compile('^(\d+) \(X-GM-MSGID (\d+) UID (\d+)\)$')

        typ, num = self.imap.select('"%s"' % folder, readonly=True)
        if typ != 'OK':
            raise Exception("Couldnt select folder %s" % folder)
        num = int(num[0])

        # Fetch interesting metadata about all mails in that mailbox
#        typ, data = self.imap.fetch('1:*', '(UID X-GM-MSGID BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
        typ, data = self.imap.fetch('1:*', '(UID X-GM-MSGID)')

        # Just keeping that around: usefull to set the seen parameter in maildir filenames:
#        typ, data = imap.fetch(num, '(FLAGS)') # \\Seen
        if typ != 'OK':
            raise Exception("Couldnt fetch mails from folder %s" % folder)

        mails = {}
        for f in data:
            if f is None: # empty mailbox
                break
            m = reg.search(f)
            if m:
                id, msgid, uid = int(m.group(1)), int(m.group(2)), int(m.group(3))
                mails[uid] = (msgid, id)
#        print '%s (%d) got metadata from %d messages' % (folder, fuid, count)
        return mails

    def get_size(self, meta):
        m = self.re_size.search(meta)
        return int(int(m.group(1)) / 1024)

    def get_mail(self, id):
        typ, data = self.imap.fetch(id, '(RFC822)')
        if typ != 'OK':
            raise Exception("Couldnt fetch email %d" % id)
        meta = data[0][0]
        msg = data[0][1]
        size = self.get_size(meta)
        return size, data[0][1]


class Database:
    def __init__(self, username=False):
        if not os.path.exists(username):
            os.mkdir(username)
        db = os.path.join(username, 'gmail.sqlite')
        self.connect(db)

    def connect(self, dbfile):
        exist = True
        if not os.path.exists(dbfile):
            exist = False
        db = sqlite3.connect(dbfile)

        if exist is False:
            print 'creating db', dbfile
            folders = "CREATE TABLE folders (name text, uid integer)"
            mails = "CREATE TABLE mails (uid integer, msgid integer, folder_uid integer)"
            db.execute(folders)
            db.execute(mails)
            db.commit()
        self.db = db

    def get_folders(self):
        q = "SELECT uid, name FROM folders"
        r = self.db.execute(q)
        f = r.fetchall()
        folders = {}
        for d in f:
            uid, name = d
            folders[int(uid)] = name
        return folders

    def get_mails(self, folder_uid):
        q = "SELECT uid, msgid FROM mails WHERE folder_uid = ?"
        r = self.db.execute(q, (folder_uid,))
        m = r.fetchall()
        mails = {}
        for d in m:
            uid, msgid = d
            mails[int(uid)] = int(msgid)
        return mails

    # Folders management
    def update_folder(self, uid, name):
        q = "UPDATE folders SET name = ? WHERE uid = ?"
        r = self.db.execute(q, (name, uid))
        self.db.commit()
    def insert_folder(self, uid, name):
        q = "INSERT INTO folders (uid, name) VALUES (?, ?)"
        r = self.db.execute(q, (uid, name))
        self.db.commit()
    def delete_folder(self, uid):
        q = "DELETE FROM folders WHERE uid = ?"
        r = self.db.execute(q, (uid, ))
        self.db.commit()

    # Get fuid and uid from a gmail msgid
    def get_original(self, msgid):
        # Cause even Sent Mails comes from All Mail:
        q = "SELECT uid FROM mails WHERE msgid = ? AND folder_uid = 1"
        r = self.db.execute(q, (msgid, ))
        m = r.fetchone()
        fuid, uid = None, None
        if m:
            fuid = 1
            (uid, ) = m
        return fuid, uid

    # Mails management
    def insert_mail(self, uid, msgid, folder_uid):
        q = "INSERT INTO mails (uid, msgid, folder_uid) VALUES (?, ?, ?)"
        r = self.db.execute(q, (uid, msgid, folder_uid))
#        self.db.commit()
    def delete_mail(self, uid, folder_uid):
        q = "DELETE FROM mails WHERE uid = ? AND folder_uid = ?"
        r = self.db.execute(q, (uid, folder_uid))
#        self.db.commit()
    def commit(self):
        self.db.commit()

class Maildir:
    def __init__(self, username):
        self.mbox = {}
        # We create the root of the mailboxes, the INBOX dir:
        self.root = mailbox.Maildir(os.path.join(username, 'Maildir'))

    # Manage folders (called mailboxes)
    def load_folder(self, uid, name):
        if name == 'INBOX':
            self.mbox[uid] = self.root
        else:
            name = name.replace('/', '.')
            self.mbox[uid] = self.root.get_folder(name)
    def add_folder(self, uid, name):
        if name == 'INBOX':
            self.mbox[uid] = self.root
        else:
            name = name.replace('/', '.')
            self.mbox[uid] = self.root.add_folder(name)
    def del_folder(self, name):
        print 'delete folder', name
        name = name.replace('/', '.')
        mbox = self.root.get_folder(name)
        print 'remove all emails'
        mbox.clear()
        print 'remove directory', name
        self.root.remove_folder(name)
    def mov_folder(self, uid, src, dst):
        src = src.replace('/', '.')
        dst = dst.replace('/', '.')
        mbox = self.root.get_folder(src)
        src_path = mbox._path
        dst_path = os.path.join(os.path.dirname(src_path), '.' + dst)
        os.rename(src_path, dst_path)
        self.mbox[uid] = self.root.get_folder(dst)

    # Manage mails
    def add_mail(self, fuid, uid, msg):
#        print 'adding email %d / %d' % (fuid, uid)
        if not fuid in self.mbox:
            raise Exception('ERROR: loading mbox with UID %d doesnt exist' % fuid)
        path = os.path.join(self.mbox[fuid]._path, 'cur', str(uid))
        if os.path.exists(path):
            print 'WARNING: %s exists' % path

        # If its part of GMAIL/All Mail, we write the file, otherwise we link (check Sent mails)
        fd = open(path, 'w')
        fd.write(msg)
        fd.close()

    # Link a new mail to an existing email file
    def link_mail(self, fuid, uid, src_fuid, src_uid):
        src = os.path.join(self.mbox[src_fuid]._path, 'cur', str(src_uid))
        dst = os.path.join(self.mbox[fuid]._path, 'cur', str(uid))
        if not os.path.exists(src):
            raise Exception("Source file doesnt exist: %s" % src)
        if not os.path.exists(dst): # In case of ctrl+C:
#            raise Exception("Destination file does exist: %s" % dst)
            os.link(src, dst)

    def del_mail(self, uid, fuid):
        path = os.path.join(self.mbox[fuid]._path, 'cur', str(uid))
        if os.path.exists(path):
            os.unlink(path)


# Main program
##

db = Database(username)
dbFolders = db.get_folders()

mdir = Maildir(username)

gmail = Gmail(username=username, password=password)
imapFolders = gmail.get_folders()

### Folders
for k in dbFolders:
    # Deleting non existing folders
    if not k in imapFolders:
        print '[-] deleting %s (%d)' % (dbFolders[k], k)
        db.delete_folder(k)
        mdir.del_folder(dbFolders[k])

# We NEED to have [Gmail]/All Mail first since all original files will be there (uid= 1)
keys = imapFolders.keys()
keys.sort()
for k in keys:
    # If folder was renamed
    if k in dbFolders and dbFolders[k] != imapFolders[k]:
        print '[c] moving %s -> %s (%d)' % (dbFolders[k], imapFolders[k], k)
        db.update_folder(k, imapFolders[k])
        mdir.mov_folder(k, dbFolders[k], imapFolders[k])
    # If folder doesnt exist
    elif not k in dbFolders:
        print '[+] adding %s (%d)' % (imapFolders[k], k)
        db.insert_folder(k, imapFolders[k])
        mdir.add_folder(k, imapFolders[k])
    else:
#        print '[=] loading %s (%d)' % (imapFolders[k], k)
        mdir.load_folder(k, imapFolders[k])

#    continue

    ### Mails
    dbMails = db.get_mails(k)
    imapMails = gmail.get_mails(imapFolders[k], k)
    print '[i] checking %s (%d) - emails: %d (local) %d (imap)' % (
        imapFolders[k], k, len(dbMails), len(imapMails))

    # Create new mails
    count = 0
    totalSize = 0
    import sys
    for uid in imapMails:
        if not uid in dbMails:
            if count != 0 and (count % 200) == 0:
                db.commit()
                status = '[+] added %d emails (%d KB downloaded)' % (count, totalSize)
                print status

            msgid, id = imapMails[uid]

            # Check if the email was already downloaded somewhere:
            if k != 1: # Different from All Mails:
                src_fuid, src_uid = db.get_original(msgid)
                if not src_fuid is None:
                    mdir.link_mail(k, uid, src_fuid, src_uid)
            else:
                # We need to create a new email:
                size, mail = gmail.get_mail(id)
                totalSize += size
                mdir.add_mail(k, uid, mail)

            # only after the mail was inserted:
            db.insert_mail(uid, msgid, k)

            count += 1

    # Make sure to commit whats undone.. if emails were created
    if count > 0:
        db.commit()
        print '[+] added %d emails (%d KB downloaded)' % (count, totalSize)


    # Delete removed mails
    count = 0
    for uid in dbMails:
        if not uid in imapMails:
            if count != 0 and (count % 100) == 0:
                db.commit()
                print '[+] deleted %d emails' % count
            db.delete_mail(uid, k)
            mdir.del_mail(uid, k)
            count += 1

    if count > 0:
        db.commit()
        print '[+] deleted %d emails' % count

gmail.logout()
