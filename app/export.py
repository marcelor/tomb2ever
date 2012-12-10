from lxml import etree
from cStringIO import StringIO
import glob
import time
import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.type.ttypes as Types

from local_settings import EVERNOTE_AUTHTOKEN

# Real applications authenticate with Evernote using OAuth, but for the
# purpose of exploring the API, you can get a developer token that allows
# you to access your own Evernote account. To get a developer token, visit
# https://sandbox.evernote.com/api/DeveloperToken.action
authToken = EVERNOTE_AUTHTOKEN

if authToken == "your developer token":
    print "Please fill in your developer token"
    print "To get a developer token, visit " \
        "https://sandbox.evernote.com/api/DeveloperToken.action"
    exit(1)

# Initial development is performed on our sandbox server. To use the production
# service, change "sandbox.evernote.com" to "www.evernote.com" and replace your
# developer token above with a token from
# https://www.evernote.com/api/DeveloperToken.action
evernoteHost = "sandbox.evernote.com"
userStoreUri = "https://" + evernoteHost + "/edam/user"

userStoreHttpClient = THttpClient.THttpClient(userStoreUri)
userStoreProtocol = TBinaryProtocol.TBinaryProtocol(userStoreHttpClient)
userStore = UserStore.Client(userStoreProtocol)

versionOK = userStore.checkVersion("Evernote EDAMTest (Python)",
                                   UserStoreConstants.EDAM_VERSION_MAJOR,
                                   UserStoreConstants.EDAM_VERSION_MINOR)
print "Is my Evernote API version up to date? ", str(versionOK)
print ""
if not versionOK:
    exit(1)

###################

noteStoreUrl = userStore.getNoteStoreUrl(authToken)

noteStoreHttpClient = THttpClient.THttpClient(noteStoreUrl)
noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
noteStore = NoteStore.Client(noteStoreProtocol)

# Create notebook to store the Tomboy notes
notebook = Types.Notebook()
notebook.name = 'Notes imported from Tomboy'
notebook.active = True
try:
    created_notebook = noteStore.createNotebook(authToken, notebook)
except:
    print 'A notebook with the same name already exists'
    exit(1)

def dateToTimestamp(date):
    ymd, hmstz = date.split('T')
    year, month, day = ymd.split('-')
    hms, tz = hmstz.split('-')
    hour, minutes, seconds = hms.split(':')
    seconds, microseconds = seconds.split('.')

    date = '%s-%s-%sT%s:%s:%s.%s' % (year, month, day, hour, minutes, seconds, microseconds[:6])

    time_from_date = time.mktime(time.strptime(date, '%Y-%m-%dT%H:%M:%S.%f'))

    return time_from_date

def createNote(title, content, created, updated):
    note = Types.Note()
    note.title = title

    note.content = '<?xml version="1.0" encoding="UTF-8"?>'
    note.content += '<!DOCTYPE en-note SYSTEM ' \
        '"http://xml.evernote.com/pub/enml2.dtd">'
    note.content += '<en-note>'
    note.content += content.replace('\n', '<br/>').replace(' ', '&nbsp;')
    note.content += '</en-note>'
    note.created = created * 1000 # Evernote timestamps are expressed in miliseconds
    note.updated = updated * 1000
    note.notebookGuid = created_notebook.guid

    createdNote = noteStore.createNote(authToken, note)

    print 'Successfully created a new note with title "%s" and GUID %s\n' % (title, createdNote.guid)

errorlog = open('./error.log', 'w')

for note in glob.glob('notes/*.note'):
    try:
        print 'Processing note %s' % note

        fd = open(note, 'r')
        xml = fd.read()
        fd.close()

        # Remove internal links as they confuse the parser
        cleaned_xml = xml.replace('<link:internal>', '').replace('</link:internal>', '')

        for event, node in etree.iterparse(StringIO(cleaned_xml)):
            if node.tag == '{http://beatniksoftware.com/tomboy}title':
                title = node.text.encode('utf-8')
            elif node.tag == '{http://beatniksoftware.com/tomboy}note-content':
                content = node.text and node.text.encode('utf-8').replace(title, '', 1) or ''
            elif node.tag == '{http://beatniksoftware.com/tomboy}create-date':
                created = dateToTimestamp(node.text.encode('utf-8'))
            elif node.tag == '{http://beatniksoftware.com/tomboy}last-change-date':
                updated = dateToTimestamp(node.text.encode('utf-8'))

        createNote(title, content, created, updated)
    except Exception, e:
        errorlog.write('%s %s\n' % (note, str(e)))
        print 'Fail.\n'

errorlog.close()