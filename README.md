# gmail2maildir

Python script to backup / convert a Gmail account into a Maildir from IMAP

## Benefits

* Detects renamed labels (thanks to unique UIDVALIDITY identifiers)
* Doesn't waste place by using link() to point to original emails contained in [Gmail]/All Mail
* Synchronizes the whole account (contrary to some tools that just fetch the last emails): delete locally remotely deleted emails

## Notes

* This will not respect the standard Maildir email filename format which is TIMESTAMP.MICROSEC.HOSTNAME but use UID instead
* This won't work on IMAP servers where mailboxes share / can share the same UIDVALIDITY

## Quick start

You can either edit gmail2maildir.py to hardcode your username / password at the beginning or launch the script to get more instructions:

``` shell
$ ./gmail2maildir.py 
You should create a file .account with the following format:
your email::your password
```

And once its done:

``` shell
$ ./gmail2maildir.py 
[i] connected with username@gmail.com on imap.gmail.com:993
[i] checking [Gmail]/All Mail (1) - emails: 13107 (local) 13102 (imap)
[+] deleted 5 emails
[i] checking INBOX (2) - emails: 17 (local) 17 (imap)
[i] checking lescigales (77) - emails: 600 (local) 2363 (imap)
[+] added 200 emails (0 KB downloaded)
[+] added 400 emails (0 KB downloaded)
[+] added 600 emails (0 KB downloaded)
[+] added 800 emails (0 KB downloaded)
[+] added 1000 emails (0 KB downloaded)
[+] added 1200 emails (0 KB downloaded)
[+] added 1400 emails (0 KB downloaded)
[+] added 1600 emails (0 KB downloaded)
[+] added 1763 emails (0 KB downloaded)
[i] checking monit (13) - emails: 3 (local) 0 (imap)
[+] deleted 3 emails
[i] checking rsbac (76) - emails: 109 (local) 107 (imap)
[+] deleted 2 emails

```

Uses sqlite3, mailbox and imaplib Python modules.


## Moving your Maildir directory

After moving your maildir directory (changing box or fs or hard drive), to avoid start over downloading all emails from Google just do the following:
* delete all records in ./email/gmail.sqlite table mails: DELETE FROM mails WHERE folder_uid != 1 (folder_uid = 1 being the '[Gmail]/All Mails' mailbox)
* delete all emails under all mailboxes except the 'username/Maildir/.[Gmail].All Mails' one

Or simply:

``` shell
$ ./gmail2maildir.py clean

```

Come to think about it, do it BEFORE moving your directory elsewhere.


## Crontab

Stealth mode baby:

``` shell
$ ./gmail2maildir.py quiet
$
```

