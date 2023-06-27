# -*- coding: utf-8 -*-
# Copyright 2015-2023 Lenovo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Provide constants used in the elfinder api."""
# API requests constants
API_CMD = "cmd"
API_CONTENT = "content"
API_CURRENT = "current"
API_CUT = "cut"
API_CHUNK = "chunk"
API_CID = "cid"
API_DIRS = "dirs[]"
API_DOWNLOAD = "download"
API_DST = "dst"
API_HEIGHT = "height"
API_INIT = "init"
API_INTERSECT = "intersect[]"
API_MAKEDIR = "makedir"
API_MIMES = "mimes"
API_NAME = "name"
API_Q = "q"
API_RANGE = "range"
API_SRC = "src"
API_SUBSTITUTE = "substitute"
API_TARGET = "target"
API_TARGETS = "targets[]"
API_TREE = "tree"
API_TYPE = "type"
API_UPLOAD = "upload[]"
API_UPLOAD_PATH = "upload_path[]"
API_WIDTH = "width"

# Archive constants
ARCHIVE_ARGC = "argc"
ARCHIVE_CMD = "cmd"
ARCHIVE_EXT = "ext"

# Info constants
INFO_ALIAS = "alias"
INFO_DIM = "dim"
INFO_DIRS = "dirs"
INFO_HASH = "hash"
INFO_LINK = "link"
INFO_LOCKED = "locked"
INFO_MIME = "mime"
INFO_NAME = "name"
INFO_PHASH = "phash"
INFO_READ = "read"
INFO_RESIZE = "resize"
INFO_SIZE = "size"
INFO_TMB = "tmb"
INFO_TS = "ts"
INFO_URL = "url"
INFO_VOLUMEID = "volumeid"
INFO_WRITE = "write"

# Response constants
R_ADDED = "added"
R_API = "api"
R_CHANGED = "changed"
R_CHUNKMERGED = "_chunkmerged"
R_CWD = "cwd"
R_DEBUG = "debug"
R_DIM = "dim"
R_DIR_CNT = "dirCnt"
R_ERROR = "error"
R_FILE_CNT = "fileCnt"
R_FILES = "files"
R_HASHES = "hashes"
R_IMAGES = "images"
R_LIST = "list"
R_NAME = "_name"
R_NETDRIVERS = "netDrivers"
R_OPTIONS = "options"
R_REMOVED = "removed"
R_SIZE = "size"
R_SIZES = "sizes"
R_TREE = "tree"
R_UPLMAXFILE = "uplMaxFile"
R_UPLMAXSIZE = "uplMaxSize"
R_WARNING = "warning"


# Response options constants
R_OPTIONS_ARCHIVERS = "archivers"
R_OPTIONS_COPY_OVERWRITE = "copyOverwrite"
R_OPTIONS_CREATE = "create"
R_OPTIONS_CREATE_EXT = "createext"
R_OPTIONS_DISABLED = "disabled"
R_OPTIONS_DISP_INLINE_REGEX = "dispInlineRegex"
R_OPTIONS_EXTRACT = "extract"
R_OPTIONS_I18N_FOLDER_NAME = "i18nFolderName"
R_OPTIONS_JPG_QUALITY = "jpgQuality"
R_OPTIONS_MIME_ALLOW = "allow"
R_OPTIONS_MIME_DENY = "deny"
R_OPTIONS_MIME_FIRST_ORDER = "firstOrder"
R_OPTIONS_PATH = "path"
R_OPTIONS_SEPARATOR = "separator"
R_OPTIONS_SYNC_CHK_AS_TS = "syncChkAsTs"
R_OPTIONS_SYNC_MIN_MS = "syncMinMs"
R_OPTIONS_TMB_URL = "tmbURL"
R_OPTIONS_UI_CMD_MAP = "uiCmdMap"
R_OPTIONS_UPLOAD_MAX_CONN = "uploadMaxConn"
R_OPTIONS_UPLOAD_MAX_SIZE = "uploadMaxSize"
R_OPTIONS_UPLOAD_MIME = "uploadMime"
R_OPTIONS_UPLOAD_OVERWRITE = "uploadOverwrite"
R_OPTIONS_URL = "url"
