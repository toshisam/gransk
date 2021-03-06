#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import subprocess
import shutil
import chardet

import gransk.core.abstract_subscriber as abstract_subscriber
import gransk.core.helper as helper
import gransk.core.document as document


class Subscriber(abstract_subscriber.Subscriber):
  """
  Class for unpacking archives using 7zip. The archive is first written to
  a temporary directory, before 7zip is started using ``subprocess``. Each
  of the unpacked files are then added to the pipeline as individual
  documents."""
  CONSUMES = [helper.ARCHIVE]

  def setup(self, config):
    """
    Make sure temporary directory exists.

    :param config: Configuration object.
    :type config: ``dict``
    """
    self.config = config
    self.tmp_root = os.path.join(config[helper.DATA_ROOT], 'archives', '.tmp')
    self.wid = config[helper.WORKER_ID]
    if not os.path.exists(self.tmp_root):
      try:
        os.makedirs(self.tmp_root)
      except OSError as err:
        print (err)
    self.password = 'X'

  def consume(self, doc, payload):
    """
    Writes payload to disk and unpack archive using 7zip. Then adds all
    unpacked files to the pipeline.

    :param doc: Document object.
    :param payload: File pointer beloning to document.
    :type doc: ``gransk.core.document.Document``
    :type payload: ``file``
    """
    tag = self.config[helper.TAG]
    if doc.tag:
      tag = doc.tag

    filename = os.path.basename(doc.path)

    unique_filename = u'%s-%s' % (doc.docid[0:8], filename)
    unpack_to = os.path.join(
        self.config[helper.DATA_ROOT], u'archives', unique_filename)

    try:
      os.makedirs(unpack_to)
    except OSError:
      pass

    tmp_path = os.path.join(self.tmp_root, '%s.%s' % (self.wid, doc.ext))

    with open(tmp_path, 'wb') as out:
      payload.seek(0)
      out.write(payload.read())
      payload.seek(0)

    cmd = self._get_cmd(tmp_path, unpack_to)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()

    if err:
      doc.meta['archive_error'] = err.decode('utf-8')

    for folder, _, filenames in os.walk(unpack_to):
      for filename in filenames:
        path = os.path.join(folder, filename)
        new_doc = document.get_document(path, parent=doc)
        new_doc.tag = doc.tag
        with open(path) as file_object:
          self.produce(helper.PROCESS_FILE, new_doc, file_object)
          doc.children += 1

    shutil.rmtree(unpack_to)

  def _get_cmd(self, path, decompress_to):
    filename = path.encode('utf-8')
    if isinstance(filename, str):
      enc = chardet.detect(filename).get('encoding')
      filename = filename.decode(enc)

    return [u'7z', u'e', '-p%s' % self.password, u'-y', u'-o%s' % decompress_to, filename]
