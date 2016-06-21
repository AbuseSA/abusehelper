# A bot that joins channels and archives the events is sees. Creates
# files into the given archive directory, one file per channel and
# named after the channel. Each event takes one line, and the format
# is as follows:
# 2010-12-09 15:11:34Z a=1,b=2,b=3
# 2010-12-09 17:12:32Z a=4,a=5,b=6

from __future__ import absolute_import

import os
import time
import errno
import calendar

import idiokit
from . import bot, taskfarm, events


def isoformat(seconds=None, format="%Y-%m-%d %H:%M:%SZ"):
    """
    Return the ISO 8601 formatted timestamp based on the time
    expressed in seconds since the epoch. Use time.time() if seconds
    is not given or None.

    >>> isoformat(0)
    '1970-01-01 00:00:00Z'
    """

    return time.strftime(format, time.gmtime(seconds))


def isoparse(timestring, formats=("%Y-%m-%d %H:%M:%SZ", "%Y-%m-%d %H:%M:%S")):
    """
    >>> isoparse('1970-01-01 00:00:00Z')
    0

    Also support backwards compatible timestamp format:

    >>> isoparse('1970-01-01 00:00:00')
    0
    """

    for format in formats:
        try:
            time_tuple = time.strptime(timestring, format)
        except ValueError:
            continue
        else:
            return calendar.timegm(time_tuple)
    return None


def ensure_dir(dir_name):
    """
    Ensure that the directory exists (create if necessary) and return
    the absolute directory path.
    """

    dir_name = os.path.abspath(dir_name)
    try:
        os.makedirs(dir_name)
    except OSError, (code, error_str):
        if code != errno.EEXIST:
            raise
    return dir_name


class ArchiveReader(object):
    def __init__(self, fileobj):
        self._fileobj = fileobj

    def __iter__(self):
        for line in self._fileobj:
            pieces = line.split(" ", 2)
            if len(pieces) < 3:
                raise ValueError("unknown line format")
            timestamp = isoparse(pieces[0] + " " + pieces[1])
            yield timestamp, events.Event.from_unicode(pieces[2].decode("utf-8"))


class ArchiveBot(bot.ServiceBot):
    archive_dir = bot.Param("directory where archive files are written")
    bot_state_file = None

    def __init__(self, *args, **keys):
        super(ArchiveBot, self).__init__(*args, **keys)
        self.log.warn("This bot will be deprecated in the Abusehelper 4.0.0 release. Please use abusehelper.bots.archivebot module instead.")

        self.rooms = taskfarm.TaskFarm(self.handle_room, grace_period=0.0)
        self.archive_dir = ensure_dir(self.archive_dir)

    @idiokit.stream
    def handle_room(self, name):
        msg = "room {0!r}".format(name)
        attrs = events.Event(type="room", service=self.bot_name, room=unicode(name))

        with self.log.stateful(repr(self.xmpp.jid), "room", repr(name)) as log:
            log.open("Joining " + msg, attrs, status="joining")
            room = yield self.xmpp.muc.join(name, self.bot_name)

            log.open("Joined " + msg, attrs, status="joined")
            try:
                room_jid = room.jid.bare()
                yield room | events.stanzas_to_events() | self.collect(room_jid)
            finally:
                log.close("Left " + msg, attrs, status="left")

    @idiokit.stream
    def session(self, state, src_room):
        src_jid = yield self.xmpp.muc.get_full_room_jid(src_room)
        yield self.rooms.inc(src_jid.bare())

    def collect(self, room_name):
        collect = self._collect(room_name)
        idiokit.pipe(self._alert(), collect)
        return collect

    @idiokit.stream
    def _alert(self, flush_interval=2.0):
        while True:
            yield idiokit.sleep(flush_interval)
            yield idiokit.send()

    @idiokit.stream
    def _collect(self, room_name):
        path = None
        archive = None
        needs_flush = False
        init_done = False

        try:
            while True:
                event = yield idiokit.next()

                if event is None:
                    if needs_flush:
                        self.archive_flush(archive)
                    needs_flush = False
                    continue

                timestamp = time.time()
                new_path = self.archive_path(timestamp, room_name, event)
                if new_path != path:
                    if init_done:
                        self.archive_flush(archive)
                        self.archive_close(archive)
                        init_done = False
                        needs_flush = False
                        self.log.info("Closed archive {0!r}".format(path))

                    archive = self.archive_open(os.path.join(self.archive_dir, new_path))
                    path = new_path
                    init_done = True
                    self.log.info("Opened archive {0!r}".format(path))

                self.archive_write(archive, timestamp, room_name, event)
                needs_flush = True
        finally:
            if init_done:
                self.archive_flush(archive)
                self.archive_close(archive)
                self.log.info("Closed archive {0!r}".format(path))

    # Override these for custom behavior

    def archive_path(self, timestamp, room_name, event):
        return unicode(room_name).encode("utf-8")

    def archive_open(self, full_path):
        return open(full_path, "ab")

    def archive_write(self, archive, timestamp, room_name, event):
        data = unicode(event).encode("utf-8")
        archive.write(isoformat(timestamp) + " " + data + os.linesep)

    def archive_flush(self, archive):
        archive.flush()

    def archive_close(self, archive):
        archive.close()

if __name__ == "__main__":
    ArchiveBot.from_command_line().execute()
