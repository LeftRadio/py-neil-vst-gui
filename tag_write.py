
import os
import sys
import re
import logging
import argparse
import datetime
import base64
from string import Formatter
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC, Picture
from mutagen.wave import WAVE
from PIL import ImageFont, ImageDraw,  Image


__version__ = "1.25"


class TagWriter(object):
    """docstring for TagWriter"""
    def __init__(self, logger=None):
        if not logger:
            logger = logging.getLogger(__file__)
            logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                fmt='%(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
            logger.addHandler(handler)
        self.logger = logger

    def picture_write(self, image_filepath):
        """ """
        h = open(image_filepath, "rb")
        data = h.read()
        h.close()

        width, height = ( Image.open(image_filepath).convert('RGBA') ).size

        picture = Picture()
        picture.data = data
        picture.type = 18
        picture.desc = u"A bright coloured fish"
        picture.mime = u"image/png"
        picture.width = width
        picture.height = height
        picture.depth = 32

        picture_data = picture.write()
        encoded_data = base64.b64encode(picture_data)
        vcomment_value = encoded_data.decode("ascii")

        return vcomment_value

    def write(self, filepath, author, artist, sound_designer, album, genre, date, comment, image):

        if filepath.endswith('.ogg'):
            tag = OggVorbis(filepath)
        elif filepath.endswith('.flac'):
            tag = FLAC(filepath)
        else:
            tag = WAVE(filepath)

        file_basename = os.path.basename(filepath)

        self.logger.info( "TAG START [%s]" % file_basename )
        self.logger.info( "length: %s" % datetime.timedelta(seconds=tag.info.length) )

        self.logger.debug( "TAG SOURCE:" )
        self.logger.debug( "tracknumber: %s" % tag.get('tracknumber', '') )
        self.logger.debug( "title: %s" % tag.get('title', '') )
        self.logger.debug( "artist: %s" % tag.get('artist', '') )
        self.logger.debug( "album: %s" % tag.get('album', '') )
        self.logger.debug( "comment: %s" % tag.get('comment', '') )
        self.logger.debug( "genre: %s" % tag.get('genre', '') )
        self.logger.debug( "date: %s" % tag.get('date', '') )

        track_num = (re.findall(r"[-+]?\d*\.\d+|\d+", file_basename)[0]).lstrip("0")

        tag['tracknumber'] = track_num
        tag['album'] = ""
        tag['title'] = '[ глава %s ] - "%s" - %s' % (track_num, album, author)
        tag['artist'] = artist

        class CommentDefault(dict):
            def __missing__(self, key):
                return ""

        tag['comment'] = comment.format_map(
            CommentDefault(
                author=author,
                artist=artist,
                sound_designer=sound_designer
            )
        )

        tag['genre'] = genre
        tag['date'] = date


        if image is None or not os.path.exists(image):
            self.logger.info("file picture is 'None', delete data..." )
            tag["metadata_block_picture"] = ""
        else:
            self.logger.info("open [%s] image and write it to picture metadata..." % image)
            tag["metadata_block_picture"] = self.picture_write(image)

        self.logger.info("write all tags to [%s] file...  "  % file_basename)

        tag.save()

        self.logger.info("write to [%s] is OK" % file_basename)

        # debug data
        self.logger.debug( "TAG WRITEN DATA:" )
        self.logger.debug( "tracknumber: %s" % tag['tracknumber'] )
        self.logger.debug( "title: %s" % tag['title'] )
        self.logger.debug( "artist: %s" % tag['artist'] )
        self.logger.debug( "album: %s" % tag['album'] )
        self.logger.debug( "comment: %s" % tag['comment'] )
        self.logger.debug( "genre: %s" % tag['genre'] )
        self.logger.debug( "date: %s" % tag['date'] )

        self.logger.info( "TAG END [%s]"  % file_basename)


if __name__ == '__main__':

    tag_writes = TagWriter()

    FOLDER = "."

    for file in [ os.path.join(FOLDER, f) for f in os.listdir(FOLDER) if f.endswith(('.ogg', '.flac', '.wav')) ]:
        tag_writes.write(
            filepath=file,
            author='',
            artist='Олег Шубин',
            sound_designer='Владислав Каменев',
            album='',
            genre='Аудиокнига',
            date='2021',
            comment='Автор книги - {author}\n' \
                    'Читает - {artist}\n' \
                    'Звукорежиссер - {sound_designer}\n' \
                    'Проект "СВиД" - Сказки для взрослых и детей',
            image='E:/Sound/books/Роман Глушков/Холодная кровь/cover_holodnaya-krov_0.jpg'
        )
