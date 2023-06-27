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

"""Provide the connector for elFinder File Manager."""
# pylint: disable=too-many-lines

import base64
# import hashlib
import mimetypes
import os
import re
import shlex
import shutil
import subprocess
import time
import traceback
import uuid
from datetime import datetime
from types import ModuleType
from typing import Any, BinaryIO, Dict, Generator, List, Optional, Tuple, Union
from urllib.parse import quote, urljoin

from pathvalidate import sanitize_filename, sanitize_filepath
from typing_extensions import Literal, TypedDict

from .api_const import (
    API_CHUNK, API_CID, API_CMD, API_CONTENT, API_CURRENT, API_CUT, API_DIRS,
    API_DOWNLOAD, API_DST, API_HEIGHT, API_INIT, API_INTERSECT, API_MAKEDIR,
    API_MIMES, API_NAME, API_Q, API_RANGE, API_SRC, API_TARGET, API_TARGETS,
    API_TREE, API_TYPE, API_UPLOAD, API_UPLOAD_PATH, API_WIDTH, ARCHIVE_ARGC,
    ARCHIVE_CMD, ARCHIVE_EXT, R_ADDED, R_API, R_CHANGED, R_CHUNKMERGED, R_CWD,
    R_DEBUG, R_DIM, R_DIR_CNT, R_ERROR, R_FILE_CNT, R_FILES, R_HASHES,
    R_IMAGES, R_LIST, R_NAME, R_NETDRIVERS, R_OPTIONS, R_OPTIONS_ARCHIVERS,
    R_OPTIONS_COPY_OVERWRITE, R_OPTIONS_CREATE, R_OPTIONS_CREATE_EXT,
    R_OPTIONS_DISABLED, R_OPTIONS_DISP_INLINE_REGEX, R_OPTIONS_EXTRACT,
    R_OPTIONS_I18N_FOLDER_NAME, R_OPTIONS_JPG_QUALITY, R_OPTIONS_MIME_ALLOW,
    R_OPTIONS_MIME_DENY, R_OPTIONS_MIME_FIRST_ORDER, R_OPTIONS_PATH,
    R_OPTIONS_SEPARATOR, R_OPTIONS_SYNC_CHK_AS_TS, R_OPTIONS_SYNC_MIN_MS,
    R_OPTIONS_TMB_URL, R_OPTIONS_UI_CMD_MAP, R_OPTIONS_UPLOAD_MAX_CONN,
    R_OPTIONS_UPLOAD_MAX_SIZE, R_OPTIONS_UPLOAD_MIME,
    R_OPTIONS_UPLOAD_OVERWRITE, R_OPTIONS_URL, R_REMOVED, R_SIZE, R_SIZES,
    R_TREE, R_UPLMAXFILE, R_UPLMAXSIZE, R_WARNING,
)

COMMANDS = {
    "archive": "__archive",
    "chmod": "__chmod",
    "dim": "__dim",
    "duplicate": "__duplicate",
    "extract": "__extract",
    "file": "__file",
    "get": "__get",
    "info": "__places",
    "ls": "__ls",
    "mkdir": "__mkdir",
    "mkfile": "__mkfile",
    "netmount": "__netmount",
    "open": "__open",
    "parents": "__parents",
    "paste": "__paste",
    "ping": "__ping",
    "put": "__put",
    "reload": "__reload",  # not implemented
    "rename": "__rename",
    "resize": "__resize",
    "rm": "__rm",
    "search": "__search",
    "size": "__size",
    "tmb": "__thumbnails",
    "tree": "__tree",
    "upload": "__upload",
    "zipdl": "__zipdl",
}

MIME_TYPES = {
    # text
    ".cfg": "text/plain",
    ".conf": "text/plain",
    ".css": "text/css",
    ".htm": "text/html",
    ".html": "text/html",
    ".ini": "text/plain",
    ".java": "text/x-java-source",
    ".js": "text/javascript",
    ".md": "text/markdown",
    ".php": "text/x-php",
    ".pl": "text/x-perl",
    ".py": "text/x-python",
    ".rb": "text/x-ruby",
    ".rtf": "text/rtf",
    ".rtfd": "text/rtfd",
    ".sh": "text/x-shellscript",
    ".sql": "text/x-sql",
    ".txt": "text/plain",
    # apps
    ".7z": "application/x-7z-compressed",
    ".doc": "application/msword",
    ".ogg": "application/ogg",
    # video
    ".mkv": "video/x-matroska",
    ".ogm": "application/ogm",
}

Archivers = TypedDict(  # pylint: disable=invalid-name
    "Archivers",
    {"create": Dict[str, Dict[str, str]], "extract": Dict[str, Dict[str, str]]},
)
Info = TypedDict(  # pylint: disable=invalid-name
    "Info",
    {
        "alias": str,
        "dim": str,
        "dirs": int,
        "hash": str,
        "link": str,
        "locked": int,
        "mime": str,
        "name": str,
        "path": str,
        "phash": str,
        "read": int,
        "size": int,
        "tmb": str,
        "ts": float,
        "url": str,
        "volumeid": str,
        "write": int,
    },
    total=False,
)
Options = TypedDict(  # pylint: disable=invalid-name
    "Options",
    {
        "archive_mimes": List[str],
        "archivers": Archivers,
        "base_url": str,
        "debug": bool,
        "defaults": Dict[str, bool],
        "dir_mode": Literal[493],
        "dir_size": bool,
        "disabled": List[str],
        "dot_files": bool,
        "expose_real_path": bool,
        "file_mode": Literal[420],
        "file_url": bool,
        "files_url": str,
        "img_lib": Optional[str],
        "max_folder_depth": int,
        "perms": Dict[str, Dict[str, bool]],
        "root_alias": str,
        "root": str,
        "tmb_at_once": int,
        "tmb_dir": Optional[str],
        "tmb_size": int,
        "upload_allow": List[str],
        "upload_deny": List[str],
        "upload_max_conn": int,
        "upload_max_size": int,
        "upload_order": List[Literal["deny", "allow"]],
        "upload_write_chunk": int,
    },
)


def exception_to_string(excp: Exception) -> str:
    """Convert exception to string."""
    stack = traceback.extract_stack()[:-3] + traceback.extract_tb(
        excp.__traceback__
    )  # add limit=??
    pretty = traceback.format_list(stack)
    return "".join(pretty) + "\n  {} {}".format(excp.__class__, excp)


class Connector:
    """Connector for elFinder."""

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    # The options need to be persistent between connector instances.
    _options = {
        "archive_mimes": [],
        "archivers": {"create": {}, "extract": {}},
        "base_url": "",
        "debug": False,
        "defaults": {"read": True, "write": True, "rm": True},
        "dir_mode": 0o755,
        "dir_size": False,
        "disabled": ["netmount", "zipdl"],
        "dot_files": False,
        "expose_real_path": False,
        "file_mode": 0o644,
        "file_url": True,
        "files_url": "",
        "img_lib": "auto",
        "max_folder_depth": 256,
        "perms": {},
        "root_alias": "HOME",
        "root": "",
        "tmb_at_once": 5,
        "tmb_dir": ".tmb",
        "tmb_size": 48,
        "upload_allow": [],
        "upload_deny": [],
        "upload_max_conn": -1,
        "upload_max_size": 256 * 1024 * 1024,
        "upload_order": ["deny", "allow"],
        "upload_write_chunk": 8192,
    }  # type: Options

    # The cache needs to be persistent between connector instances.
    _cached_path = {}  # type: Dict[str, str]

    # public variables
    http_allowed_parameters = (
        API_CHUNK,
        API_CID,
        API_CMD,
        API_CONTENT,
        API_CURRENT,
        API_CUT,
        API_DIRS,
        API_DOWNLOAD,
        API_DST,
        API_HEIGHT,
        API_INIT,
        API_MAKEDIR,
        API_NAME,
        API_Q,
        API_RANGE,
        API_SRC,
        API_TARGET,
        API_TARGETS,
        API_TREE,
        API_TYPE,
        API_UPLOAD,
        API_UPLOAD_PATH,
        API_WIDTH,
    )

    def __init__(
        self,
        root: str,
        url: str,
        base_url: str,
        upload_max_size: int,
        tmb_dir: Optional[str],
        expose_real_path: bool = False,
        dot_files: bool = False,
        debug: bool = False,
    ) -> None:
        """Set up connector instance."""
        self.volumeid = str(uuid.uuid4())

        # internal
        self._commands = dict(COMMANDS)
        self._http_header = {}  # type: Dict[str, str]
        self._http_status_code = 0
        self._request = {}  # type: Dict[str, Any]
        self._response = {}  # type: Dict[str, Any]
        self._response[R_DEBUG] = {}
        self._error_data = {}  # type: Dict[str, str]
        self._img = None  # type: Optional[ModuleType]

        # options
        self._options["root"] = self._check_utf8(root)
        self._options["upload_max_size"] = upload_max_size
        self._options["debug"] = debug
        self._options["base_url"] = (
            base_url.lstrip("/") if base_url.startswith("//") else base_url
        )
        self._options["expose_real_path"] = expose_real_path
        self._options["dot_files"] = dot_files
        self._options["files_url"] = self._check_utf8(url).rstrip("/")

        self._debug("files_url", self._options["files_url"])
        self._debug("root", self._options["root"])

        for cmd in self._options["disabled"]:
            if cmd in self._commands:
                del self._commands[cmd]

        # TODO: Move side effects out of init.
        if tmb_dir:
            thumbs_dir = os.path.join(self._options["root"], tmb_dir)
            try:
                if not os.path.exists(thumbs_dir):
                    os.makedirs(thumbs_dir)  # self._options['tmbDir'] = False
                self._options["tmb_dir"] = thumbs_dir
            except PermissionError:
                self._options["tmb_dir"] = None
                self._debug("thumbnail", " Permission denied: " + thumbs_dir)
                print(
                    "WARNING: failed to create thumbnail folder "
                    "due to permission denied, it will be disabled."
                )

    def run(
        self, http_request: Dict[str, Any]
    ) -> Tuple[int, Dict[str, str], Dict[str, Any]]:
        """Run main function."""
        start_time = time.time()
        root_ok = True
        if not os.path.exists(self._options["root"]):
            root_ok = False
            self._response[R_ERROR] = "Invalid backend configuration"
        elif not self._is_allowed(self._options["root"], "read"):
            root_ok = False
            self._response[R_ERROR] = "Access denied"

        for field in self.http_allowed_parameters:
            if field in http_request:
                self._request[field] = http_request[field]

        if root_ok and API_CMD in self._request:
            if self._request[API_CMD] in self._commands:
                cmd = self._commands[self._request[API_CMD]]
                # A missing command method should blow up here.
                func = getattr(self, "_" + self.__class__.__name__ + cmd)

                try:
                    func()
                except Exception as exc:  # pylint: disable=broad-except
                    self._response[R_ERROR] = "Command Failed: {}, Error: \n{}".format(
                        self._request[API_CMD], exc
                    )
                    traceback.print_exc()
                    self._debug("exception", exception_to_string(exc))
            else:
                self._response[R_ERROR] = "Unknown command: {}".format(
                    self._request[API_CMD]
                )

        if self._error_data:
            self._debug("errorData", self._error_data)

        if self._options["debug"]:
            self._debug("time", (time.time() - start_time))
        else:
            self._response.pop(R_DEBUG, None)

        if self._http_status_code < 100:
            self._http_status_code = 200

        if "Content-type" not in self._http_header:
            if API_CMD in self._request and self._request[API_CMD] == "upload":
                self._http_header["Content-type"] = "text/html"
            else:
                self._http_header["Content-type"] = "application/json"
        return self._http_status_code, self._http_header, self._response

    def __places(self) -> None:
        if API_TARGETS not in self._request:
            self._response[R_ERROR] = "Invalid parameters"
            return

        targets = self._request[API_TARGETS]
        files = []
        for target in targets:
            path = self._find(target)
            if path is None:
                self._set_error_data(target, "File not found")
            else:
                files.append(self._info(path))
        self._response[R_FILES] = files

    def __open(self) -> None:
        """Open file or directory."""
        path = None
        init = self._request.get(API_INIT)
        target = self._request.get(API_TARGET)
        if not init and not target:
            self._response[R_ERROR] = "Invalid parameters"
            return

        if target:
            path = self._find_dir(target)

        if init:
            self._response[R_API] = 2.1
            if not path:
                path = self._options["root"]

        if not path:
            self._response[R_ERROR] = "File not found"
            return

        if not self._is_allowed(path, "read"):
            self._response[R_ERROR] = "Access denied"
            return

        self._cwd(path)

        try:
            items = os.listdir(path)
        except PermissionError:
            self._response[R_ERROR] = "Access denied"
            return

        files = []
        for item in sorted(items):
            file_path = os.path.join(path, item)
            if self._is_accepted(item):
                info = self._info(file_path)
                files.append(info)

        self._response[R_FILES] = files

        if self._request.get(API_TREE):
            self._response[R_FILES].append(self._info(path))

        self._check_archivers()
        if not self._options["file_url"]:
            url = ""
        else:
            url = self._options["files_url"]

        self._response[R_NETDRIVERS] = []
        self._response[R_UPLMAXFILE] = 1000
        self._response[R_UPLMAXSIZE] = (
            str(self._options["upload_max_size"] / (1024 * 1024)) + "M"
        )
        thumbs_dir = self._options["tmb_dir"]
        if thumbs_dir:
            thumbs_url = self._path2url(thumbs_dir)
        else:
            thumbs_url = ""
        self._response[R_OPTIONS] = {
            R_OPTIONS_PATH: path,
            R_OPTIONS_SEPARATOR: os.path.sep,
            R_OPTIONS_URL: url,
            R_OPTIONS_DISABLED: self._options["disabled"],
            R_OPTIONS_TMB_URL: thumbs_url,
            R_OPTIONS_ARCHIVERS: {
                R_OPTIONS_CREATE: list(self._options["archivers"]["create"].keys()),
                R_OPTIONS_EXTRACT: list(self._options["archivers"]["extract"].keys()),
                R_OPTIONS_CREATE_EXT: {
                    k: self._options["archivers"]["create"][k][ARCHIVE_EXT]
                    for k in self._options["archivers"]["create"]
                },
            },
            R_OPTIONS_COPY_OVERWRITE: True,
            R_OPTIONS_UPLOAD_MAX_SIZE: self._options["upload_max_size"],
            R_OPTIONS_UPLOAD_OVERWRITE: True,
            R_OPTIONS_UPLOAD_MAX_CONN: 3,
            R_OPTIONS_UPLOAD_MIME: {
                R_OPTIONS_MIME_ALLOW: ["all"],
                R_OPTIONS_MIME_DENY: [],
                R_OPTIONS_MIME_FIRST_ORDER: R_OPTIONS_MIME_DENY,
            },
            R_OPTIONS_I18N_FOLDER_NAME: True,
            R_OPTIONS_DISP_INLINE_REGEX: "^(?:(?:image|video|audio)|application/"
            + "(?:x-mpegURL|dash\\+xml)|(?:text/plain|application/pdf)$)",
            R_OPTIONS_JPG_QUALITY: 100,
            R_OPTIONS_SYNC_CHK_AS_TS: 1,
            R_OPTIONS_SYNC_MIN_MS: 30000,
            R_OPTIONS_UI_CMD_MAP: {},
        }

    def __parents(self) -> None:
        # TODO: implement according to the spec
        # https://github.com/Studio-42/elFinder/wiki/Client-Server-API-2.1#parents
        self._response[R_TREE] = []

    def __chmod(self) -> None:
        # TODO: implement according to the spec
        # https://github.com/Studio-42/elFinder/wiki/Client-Server-API-2.1#chmod
        self._response[R_CHANGED] = []

    def __netmount(self) -> None:
        # TODO: implement according to the spec
        # https://github.com/Studio-42/elFinder/wiki/Client-Server-API-2.1#netmount
        pass

    def __zipdl(self) -> None:
        # TODO: implement according to the spec
        # https://github.com/Studio-42/elFinder/wiki/Client-Server-API-2.1#zipdl
        pass

    def __file(self) -> None:
        self._http_header["Content-type"] = "text/html"
        target = self._request.get(API_TARGET)
        if not target:
            self._response["__text"] = "Invalid parameters"
            return

        download = self._request.get(API_DOWNLOAD)
        cur_file = self._find(target)

        if not cur_file or not os.path.exists(cur_file) or os.path.isdir(cur_file):
            self._http_status_code = 404
            self._response["__text"] = "File not found"
            return

        if not self._is_allowed(cur_file, "read"):
            self._http_status_code = 403
            self._response["__text"] = "Access denied"
            return

        if os.path.islink(cur_file):
            cur_file = self._read_link(cur_file)
            if (
                not cur_file
                or not self._is_allowed(os.path.dirname(cur_file), "read")
                or not self._is_allowed(cur_file, "read")
            ):
                self._http_status_code = 403
                self._response["__text"] = "Access denied"
                return

        mime = _mimetype(cur_file)
        parts = mime.split("/", 2)

        if download:
            disp = "attachments"
        elif parts[0] == "image":
            disp = "image"
        else:
            disp = "inline"

        self._http_status_code = 200
        self._http_header["Content-type"] = mime
        self._http_header["Content-Length"] = str(os.lstat(cur_file).st_size)
        self._http_header["Content-Disposition"] = disp + ";"
        self._response["__send_file"] = cur_file

    def __rename(self) -> None:
        """Rename file or dir."""
        name = self._request.get(API_NAME)
        target = self._request.get(API_TARGET)

        if not (name and target):
            self._response[R_ERROR] = "Invalid parameters"
            return

        cur_name = self._find(target)

        if not cur_name:
            self._response[R_ERROR] = "File not found"
            return

        cur_dir = os.path.dirname(cur_name)

        if not self._is_allowed(cur_dir, "write") and self._is_allowed(cur_name, "rm"):
            self._response[R_ERROR] = "Access denied"
            return

        name = self._check_utf8(name)

        if not name or not _check_name(name):
            self._response[R_ERROR] = "Invalid name"
            return

        new_name = os.path.join(cur_dir, name)

        if os.path.exists(new_name):
            self._response[R_ERROR] = (
                "File or folder with the same name " + new_name + " already exists"
            )
            return

        self._rm_tmb(cur_name)
        try:
            os.rename(cur_name, new_name)
            self._response[R_ADDED] = [self._info(new_name)]
            self._response[R_REMOVED] = [target]
        except OSError:
            self._response[R_ERROR] = "Unable to rename file"

    def __mkdir(self) -> None:
        """Create new directory."""
        path = None
        new_dir = None
        name = self._request.get(API_NAME)
        target = self._request.get(API_TARGET)
        dirs = self._request.get(API_DIRS)

        if not target or (not name and not dirs):
            self._response[R_ERROR] = "Invalid parameters"
            return
        path = self._find_dir(target)
        if not path:
            self._response[R_ERROR] = "Invalid parameters"
            return
        if not self._is_allowed(path, "write"):
            self._response[R_ERROR] = "Access denied"
            return

        if name:
            name = self._check_utf8(name)
            if not _check_name(name):
                self._response[R_ERROR] = "Invalid name"
                return
            new_dir = os.path.join(path, name)
            if os.path.exists(new_dir):
                self._response[R_ERROR] = (
                    "File or folder with the same name " + name + " already exists"
                )
            else:
                try:
                    os.mkdir(new_dir, int(self._options["dir_mode"]))
                    self._response[R_ADDED] = [self._info(new_dir)]
                    self._response[R_HASHES] = {}
                except OSError:
                    self._response[R_ERROR] = "Unable to create folder"
        if dirs:
            self._response[R_ADDED] = []
            self._response[R_HASHES] = {}
            for sdir in dirs:
                subdir = sdir.lstrip("/")
                if not _check_dir(subdir):
                    self._response[R_ERROR] = "Invalid dir name: " + subdir
                    return

                new_subdir = os.path.join(path, subdir)
                if os.path.exists(new_subdir):
                    self._response[R_ERROR] = (
                        "File or folder with the same name "
                        + subdir
                        + " already exists"
                    )
                    return
                try:
                    os.mkdir(new_subdir, int(self._options["dir_mode"]))
                    self._response[R_ADDED].append(self._info(new_subdir))
                    self._response[R_HASHES][sdir] = self._hash(new_subdir)
                except OSError:
                    self._response[R_ERROR] = "Unable to create folder"
                    return

    def __mkfile(self) -> None:
        """Create new file."""
        name = self._request.get(API_NAME)
        target = self._request.get(API_TARGET)
        if not target or not name:
            self._response[R_ERROR] = "Invalid parameters"
            return

        name = self._check_utf8(name)
        cur_dir = self._find_dir(target)
        if not cur_dir:
            self._response[R_ERROR] = "Invalid parameters"
            return
        if not self._is_allowed(cur_dir, "write"):
            self._response[R_ERROR] = "Access denied"
            return
        if not _check_name(name):
            self._response[R_ERROR] = "Invalid name"
            return

        new_file = os.path.join(cur_dir, name)

        if os.path.exists(new_file):
            self._response[R_ERROR] = "File or folder with the same name already exists"
        else:
            try:
                open(new_file, "w").close()
                self._response[R_ADDED] = [self._info(new_file)]
            except OSError:
                self._response[R_ERROR] = "Unable to create file"

    def __rm(self) -> None:
        """Delete files and directories."""
        rm_file = rm_list = None
        if API_TARGETS in self._request:
            rm_list = self._request[API_TARGETS]

        if not rm_list:
            self._response[R_ERROR] = "Invalid parameters"
            return

        if not isinstance(rm_list, list):
            rm_list = [rm_list]

        removed = []
        for rm_hash in rm_list:
            rm_file = self._find(rm_hash)
            if not rm_file:
                continue
            if self._remove(rm_file):
                removed.append(rm_hash)
            else:
                self._response[R_ERROR] = "Failed to remove: " + rm_file
                return

        self._response[R_REMOVED] = removed

    def __upload(self) -> None:
        """Upload files."""
        try:  # Windows needs stdio set for binary mode.
            import msvcrt  # pylint: disable=import-outside-toplevel

            # pylint: disable=no-member
            # stdin  = 0
            # stdout = 1
            msvcrt.setmode(0, os.O_BINARY)  # type: ignore
            msvcrt.setmode(1, os.O_BINARY)  # type: ignore
        except ImportError:
            pass
        if API_TARGET in self._request:
            chunk = self._request.get(API_CHUNK)
            self._response[R_ADDED] = []
            self._response[R_WARNING] = []
            if chunk:
                self.__upload_large_file()
            else:
                self.__upload_small_files()
            if len(self._response[R_WARNING]) == 0:
                del self._response[R_WARNING]
        else:
            self._http_status_code = 400
            self._response[R_WARNING] = ["Invalid parameters"]

    def __upload_large_file(self) -> None:
        """Upload large files by chunks."""
        target = self._request.get(API_TARGET)
        if not target:
            self._response[R_WARNING] = "Invalid parameters"
            return
        cur_dir = self._find_dir(target)
        if not cur_dir:
            self._response[R_WARNING] = "Invalid parameters"
            return
        up_files = self._request.get(API_UPLOAD)
        if not up_files:
            self._response[R_WARNING] = "No file to upload"
            return
        chunk = self._request.get(API_CHUNK)
        if not chunk:
            self._response[R_WARNING] = "No chunk to upload"
            return
        max_size = self._options["upload_max_size"]
        upload_paths = self._request.get(API_UPLOAD_PATH)
        if upload_paths:
            upload_paths = [self._find_dir(d) for d in upload_paths]
        if upload_paths and upload_paths[0]:
            cur_dir = upload_paths[0]
        if not cur_dir:
            self._response[R_WARNING] = "Invalid upload path"
            return
        if not self._is_allowed(cur_dir, "write"):
            self._response[R_WARNING] = "Access denied"
            return
        if chunk.endswith(".part"):
            chunk_range = self._request.get(API_RANGE)
            if not chunk_range:
                self._response[R_WARNING] = "No chunk range"
                return
            start, clength, total = [int(i) for i in chunk_range.split(",")]
            name = ".".join(chunk.split(".")[:-2])
            if not self._is_upload_allow(name):
                self._set_error_data(name, "Not allowed file type")
            elif total > max_size:
                self._set_error_data(name, "File exceeds the maximum allowed filesize")
            else:
                chunk_index, total_chunks = [
                    int(i) for i in chunk.split(".")[-2].split("_")
                ]
                if not _check_name(name):
                    self._set_error_data(name, "Invalid name: " + name)
                else:
                    record_path = os.path.join(cur_dir, "." + name + ".txt")
                    file_path = os.path.join(cur_dir, name + ".parts")
                    if not os.path.exists(file_path) and os.path.exists(record_path):
                        os.remove(record_path)
                    with open(
                        file_path, "rb+" if os.path.exists(file_path) else "wb+"
                    ) as fil:
                        fil.seek(start)
                        data = up_files[0]
                        written_size = 0
                        for chunk in self._fbuffer(data.file):
                            fil.write(chunk)
                            written_size += len(chunk)
                            if written_size > clength:
                                self._set_error_data(name, "Invalid file size")
                                break

                    with open(
                        record_path, "r+" if os.path.exists(record_path) else "w+",
                    ) as fil:
                        fil.seek(chunk_index)
                        fil.write("X")
                        fil.seek(0)
                        written = fil.read()
                        if written == ("X" * (total_chunks + 1)):
                            self._response[R_ADDED] = []
                            self._response[R_CHUNKMERGED] = name
                            self._response[R_NAME] = name
                        else:
                            self._response[R_ADDED] = []
                    if R_CHUNKMERGED in self._response:
                        os.remove(record_path)
        else:
            name = chunk
            file_path = os.path.join(cur_dir, name)
            if os.path.exists(file_path + ".parts"):
                up_size = os.lstat(file_path + ".parts").st_size
                if up_size > max_size:
                    try:
                        os.unlink(file_path + ".parts")
                        self._response[R_WARNING].append(
                            "File exceeds the maximum allowed filesize"
                        )
                    except OSError:
                        # TODO ?  # pylint: disable=fixme
                        self._response[R_WARNING].append(
                            "File was only partially uploaded"
                        )
                else:
                    if self._is_upload_allow(name):
                        os.rename(file_path + ".parts", file_path)
                        os.chmod(file_path, self._options["file_mode"])
                        self._response[R_ADDED] = [self._info(file_path)]
                    else:
                        self._response[R_WARNING].append("Not allowed file type")
                        try:
                            os.unlink(file_path + ".parts")
                        except OSError:
                            pass

    def __upload_small_files(self) -> None:
        """Upload small files."""
        target = self._request.get(API_TARGET)
        if not target:
            self._response[R_WARNING] = "Invalid parameters"
            return
        cur_dir = self._find_dir(target)
        if not cur_dir:
            self._response[R_WARNING] = "Invalid parameters"
            return
        up_files = self._request.get(API_UPLOAD)
        if not up_files:
            self._response[R_WARNING] = "No file to upload"
            return
        up_size = 0
        max_size = self._options["upload_max_size"]
        upload_paths = self._request.get(API_UPLOAD_PATH)
        if upload_paths:
            upload_paths = [self._find_dir(d) for d in upload_paths]
        for idx, data in enumerate(up_files):
            name = data.filename.encode("utf-8")
            if not name:
                continue
            name = self._check_utf8(name)
            name = os.path.basename(name)
            if not upload_paths:
                target_dir = cur_dir
            else:
                target_dir = upload_paths[idx]
            if not target_dir:
                self._response[R_WARNING].append("Invalid upload path")
            elif not _check_name(name):
                self._response[R_WARNING].append("Invalid name: " + name)
            elif not self._is_allowed(target_dir, "write"):
                self._response[R_WARNING] = "Access denied"
            else:
                name = os.path.join(target_dir, name)
                replace = os.path.exists(name)
                try:
                    fil = open(name, "wb", self._options["upload_write_chunk"])
                    for chunk in self._fbuffer(data.file):
                        fil.write(chunk)
                    fil.close()
                    up_size += os.lstat(name).st_size
                    if up_size > max_size:
                        try:
                            os.unlink(name)
                            self._response[R_WARNING].append(
                                "File exceeds the maximum allowed filesize"
                            )
                        except OSError:
                            self._response[R_WARNING].append(
                                "File was only partially uploaded"
                            )
                    elif not self._is_upload_allow(name):
                        self._response[R_WARNING].append("Not allowed file type")
                        try:
                            os.unlink(name)
                        except OSError:
                            pass
                    else:
                        os.chmod(name, self._options["file_mode"])
                        if replace:  # update thumbnail
                            self._rm_tmb(name)
                        self._response[R_ADDED].append(self._info(name))

                except OSError:
                    self._response[R_WARNING].append("Unable to save uploaded file")
                if up_size > max_size:
                    try:
                        os.unlink(name)
                        self._response[R_WARNING].append(
                            "File exceeds the maximum allowed filesize"
                        )
                    except OSError:
                        self._response[R_WARNING].append(
                            "File was only partially uploaded"
                        )

    def __paste(self) -> None:
        """Copy or cut files/directories."""
        if API_TARGETS in self._request and API_DST in self._request:
            dst = self._find_dir(self._request[API_DST])
            cur_dir = dst
            if not cur_dir or not dst or API_TARGETS not in self._request:
                self._response[R_ERROR] = "Invalid parameters"
                return
            files = self._request[API_TARGETS]
            if not isinstance(files, list):
                files = [files]

            cut = False
            if API_CUT in self._request:
                if self._request[API_CUT] == "1":
                    cut = True

            if not self._is_allowed(dst, "write"):
                self._response[R_ERROR] = "Access denied"
                return

            added = []
            removed = []
            for fhash in files:
                fil = self._find(fhash)
                if not fil:
                    self._response[R_ERROR] = "File not found"
                    return
                new_dst = os.path.join(dst, os.path.basename(fil))
                if dst.find(fil) == 0:
                    self._response[R_ERROR] = "Unable to copy into itself"
                    return

                if cut:
                    if not self._is_allowed(fil, "rm"):
                        self._response[R_ERROR] = "Move failed"
                        self._set_error_data(fil, "Access denied")
                        return
                    # TODO thumbs  # pylint: disable=fixme
                    if os.path.exists(new_dst):
                        self._response[
                            R_ERROR
                        ] = "File or folder with the same name already exists"
                        self._set_error_data(
                            fil, "File or folder with the same name already exists"
                        )
                        return
                    try:
                        os.rename(fil, new_dst)
                        self._rm_tmb(fil)
                        added.append(self._info(new_dst))
                        removed.append(fhash)
                        continue
                    except OSError:
                        self._response[R_ERROR] = "Unable to move files"
                        self._set_error_data(fil, "Unable to move")
                        return
                else:
                    if not self._copy(fil, new_dst):
                        self._response[R_ERROR] = "Unable to copy files"
                        return
                    added.append(self._info(new_dst))
                    continue
            self._response[R_ADDED] = added
            self._response[R_REMOVED] = removed
        else:
            self._response[R_ERROR] = "Invalid parameters"

    def __duplicate(self) -> None:
        """Create copy of files/directories."""
        targets = self._request.get(API_TARGETS)
        if not targets:
            self._response[R_ERROR] = "Invalid parameters"
            return

        added = []
        for target in targets:
            target = self._find(target)
            if not target:
                self._response[R_ERROR] = "File not found"
                return
            cur_dir = os.path.dirname(target)
            if not self._is_allowed(target, "read") or not self._is_allowed(
                cur_dir, "write"
            ):
                self._response[R_ERROR] = "Access denied"
                return
            new_name = _unique_name(target)
            if not self._copy(target, new_name):
                self._response[R_ERROR] = "Unable to create file copy"
                return
            added.append(self._info(new_name))
        self._response[R_ADDED] = added

    def __resize(self) -> None:
        """Scale image size."""
        target = self._request.get(API_TARGET)
        width = self._request.get(API_WIDTH)
        height = self._request.get(API_HEIGHT)
        if not (target and width is not None and height is not None):
            self._response[R_ERROR] = "Invalid parameters"
            return

        width = int(width)
        height = int(height)

        if width < 1 or height < 1:
            self._response[R_ERROR] = "Invalid parameters"
            return

        cur_file = self._find(target)

        if not cur_file:
            self._response[R_ERROR] = "File not found"
            return

        if not self._is_allowed(cur_file, "write"):
            self._response[R_ERROR] = "Access denied"
            return
        if _mimetype(cur_file).find("image") != 0:
            self._response[R_ERROR] = "File is not an image"
            return

        self._debug("resize " + cur_file, str(width) + ":" + str(height))
        if not self._init_img_lib():
            return

        try:
            img = self._img.open(cur_file)  # type: ignore
            img_resized = img.resize(
                (width, height), self._img.ANTIALIAS  # type: ignore
            )
            img_resized.save(cur_file)
            self._rm_tmb(cur_file)
        except OSError as exc:  # UnidentifiedImageError requires Pillow 7.0.0
            # self._debug('resizeFailed_' + path, str(exc))
            self._debug("resizeFailed_" + self._options["root"], str(exc))
            self._response[R_ERROR] = "Unable to resize image"
            return

        self._response[R_CHANGED] = [self._info(cur_file)]

    def __thumbnails(self) -> None:
        """Create previews for images."""
        thumbs_dir = self._options["tmb_dir"]
        targets = self._request.get(API_TARGETS)
        if not targets:
            return

        if not self._init_img_lib() or not self._can_create_tmb():
            return
        assert thumbs_dir  # typing
        if self._options["tmb_at_once"] > 0:
            tmb_max = self._options["tmb_at_once"]
        else:
            tmb_max = 5
        self._response[R_IMAGES] = {}
        i = 0
        for fhash in targets:
            path = self._find(fhash)
            if path is None:
                continue
            if os.path.dirname(path) == thumbs_dir:
                continue
            if self._can_create_tmb(path) and self._is_allowed(path, "read"):
                tmb = os.path.join(thumbs_dir, fhash + ".png")
                if not os.path.exists(tmb):
                    if self._tmb(path, tmb):
                        self._response[R_IMAGES].update({fhash: self._path2url(tmb)})
                        i += 1
            if i >= tmb_max:
                break

    def __size(self) -> None:
        if API_TARGETS not in self._request:
            self._response[R_ERROR] = "Invalid parameters"
            return

        targets = self._request[API_TARGETS]

        all_total_size = 0
        all_file_count = 0
        all_dir_count = 0
        sizes = []  # type: List[Dict[str, int]]

        for target in targets:
            path = self._find(target)
            if path is None:
                self._set_error_data(target, "Target not found")
                continue
            total_size = 0
            file_count = 0
            dir_count = 0
            if os.path.isdir(path):
                for root, dirs, files in os.walk(path, topdown=True):
                    for folder in dirs:
                        folder_path = os.path.join(root, folder)
                        size = self._dir_size(folder_path)
                        sizes.append({})
                        dir_count += 1
                        total_size += size
                    for fil in files:
                        file_path = os.path.join(root, fil)
                        size = os.stat(file_path).st_size
                        total_size += size
                        file_count += 1
                    break
            else:
                size = os.stat(file_path).st_size
                total_size += size
                file_count += 1
            sizes.append(
                {R_DIR_CNT: dir_count, R_FILE_CNT: file_count, R_SIZE: total_size}
            )
            all_total_size += total_size
            all_file_count += file_count
            all_dir_count += dir_count

        self._response[R_SIZE] = all_total_size
        self._response[R_FILE_CNT] = all_file_count
        self._response[R_DIR_CNT] = all_dir_count
        self._response[R_SIZES] = sizes

    def __ls(self) -> None:
        target = self._request.get(API_TARGET)
        if not target:
            self._response[R_ERROR] = "Invalid parameters"
            return

        intersect = self._request.get(API_INTERSECT)

        path = self._find(target)
        if path is None or not os.path.isdir(path):
            self._response[R_ERROR] = "Target directory not found"
            return

        if os.path.islink(path):
            path = self._read_link(path)
            if path is None:
                self._response[R_ERROR] = "Directory (link) not found"
                return

        if not self._is_allowed(path, "read"):
            self._response[R_ERROR] = "Access denied"
            return

        try:
            file_names = os.listdir(path)
        except PermissionError:
            self._response[R_ERROR] = "Access denied"
            return

        items = {}
        for fname in file_names:
            fhash = self._hash(os.path.join(path, fname))
            if intersect:
                if fhash in intersect:
                    items[fhash] = fname
            else:
                items[fhash] = fname
        self._response[R_LIST] = items

    def __tree(self) -> None:
        """Return directory tree starting from path."""
        target = self._request.get(API_TARGET)
        if not target:
            self._response[R_ERROR] = "Invalid parameters"
            return
        path = self._find_dir(target)

        if path is None or not os.path.isdir(path):
            self._response[R_ERROR] = "Directory not found"
            return

        if os.path.islink(path):
            path = self._read_link(path)
            if path is None:
                self._response[R_ERROR] = "Directory (link) not found"
                return

        if not self._is_allowed(path, "read"):
            self._response[R_ERROR] = "Access denied"
            return

        try:
            directories = os.listdir(path)
        except PermissionError:
            self._response[R_ERROR] = "Access denied"
            return

        tree = []
        for directory in sorted(directories):
            dir_path = os.path.join(path, directory)
            if (
                os.path.isdir(dir_path)
                and not os.path.islink(dir_path)
                and self._is_accepted(directory)
            ):
                tree.append(self._info(dir_path))
        self._response[R_TREE] = tree

    def __get(self) -> None:
        target = self._request.get(API_TARGET)
        if not target:
            self._response[R_ERROR] = "Invalid parameters"
            return

        cur_file = self._find(target)

        if not cur_file:
            self._response[R_ERROR] = "File not found"
            return

        if not self._is_allowed(cur_file, "read"):
            self._response[R_ERROR] = "Access denied"
            return

        try:
            with open(cur_file, "r") as text_fil:
                self._response[API_CONTENT] = text_fil.read()
        except UnicodeDecodeError:
            with open(cur_file, "rb") as bin_fil:
                self._response[API_CONTENT] = base64.b64encode(bin_fil.read()).decode(
                    "ascii"
                )

    def __dim(self) -> None:
        target = self._request.get(API_TARGET)
        if not target:
            self._response[R_ERROR] = "Invalid parameters"
            return

        cur_file = self._find(target)

        if not cur_file:
            self._response[R_ERROR] = "File not found"
            return

        if not self._is_allowed(cur_file, "read"):
            self._response[R_ERROR] = "Access denied"
            return

        dim = self._get_img_size(cur_file)
        if dim:
            self._response[R_DIM] = str(dim)
        else:
            # FIXME This should be an error in the response instead.
            self._response[R_DIM] = None

    def __put(self) -> None:
        """Save content in file."""
        target = self._request.get(API_TARGET)
        content = self._request.get(API_CONTENT)
        if not target or not content:
            self._response[R_ERROR] = "Invalid parameters"
            return

        cur_file = self._find(target)

        if not cur_file:
            self._response[R_ERROR] = "File not found"
            return

        if not self._is_allowed(cur_file, "write"):
            self._response[R_ERROR] = "Access denied"
            return

        try:
            if (
                self._request[API_CONTENT].startswith("data:")
                and ";base64," in self._request[API_CONTENT][:100]
            ):
                img_data = self._request[API_CONTENT].split(";base64,")[1]
                img_data = base64.b64decode(img_data)
                with open(cur_file, "wb") as bin_fil:
                    bin_fil.write(img_data)
            else:
                with open(cur_file, "w+") as text_fil:
                    text_fil.write(self._request[API_CONTENT])
            self._rm_tmb(cur_file)
            self._response[R_CHANGED] = [self._info(cur_file)]
        except OSError:
            self._response[R_ERROR] = "Unable to write to file"

    def __archive(self) -> None:
        """Compress files/directories to archive."""
        # TODO: We don't support "name" field yet.
        # "name" is a parameter according to api 2.1.
        archive_type = self._request.get(API_TYPE)
        target = self._request.get(API_TARGET)
        files = self._request.get(API_TARGETS)
        if not archive_type or not target or not files:
            self._response[R_ERROR] = "Invalid parameters"
            return

        cur_dir = self._find_dir(target)
        if not cur_dir:
            self._response[R_ERROR] = "File not found"
            return

        if not self._is_allowed(cur_dir, "write"):
            self._response[R_ERROR] = "Access denied"
            return

        if (
            archive_type not in self._options["archivers"]["create"]
            or archive_type not in self._options["archive_mimes"]
        ):
            self._response[R_ERROR] = "Unable to create archive"
            return

        real_files = []
        for fhash in files:
            cur_file = self._find(fhash, cur_dir)
            if not cur_file:
                self._response[R_ERROR] = "File not found"
                return
            real_files.append(os.path.basename(cur_file))

        arc = self._options["archivers"]["create"][archive_type]
        if len(real_files) > 1:
            archive_name = "Archive"
        else:
            archive_name = real_files[0]
        archive_name += "." + arc[ARCHIVE_EXT]
        archive_name = _unique_name(archive_name, "")
        archive_path = os.path.join(cur_dir, archive_name)

        cmd = [arc[ARCHIVE_CMD]]
        for arg in arc[ARCHIVE_ARGC].split():
            cmd.append(arg)
        cmd.append(archive_name)
        for fil in real_files:
            cmd.append(fil)

        cur_cwd = os.getcwd()
        os.chdir(cur_dir)
        ret = _run_sub_process(cmd)
        os.chdir(cur_cwd)

        if not ret:
            self._response[R_ERROR] = "Unable to create archive"
            return

        self._response[R_ADDED] = [self._info(archive_path)]

    def __extract(self) -> None:
        """Extract archive."""
        target = self._request.get(API_TARGET)
        if not target:
            self._response[R_ERROR] = "Invalid parameters"
            return

        makedir = self._request.get(API_MAKEDIR)
        cur_file = self._find(target)
        if cur_file is None or os.path.isdir(cur_file):
            self._response[R_ERROR] = "File not found"
            return

        cur_dir = os.path.dirname(cur_file)

        if not self._is_allowed(cur_dir, "write"):
            self._response[R_ERROR] = "Access denied"
            return

        mime = _mimetype(cur_file)
        self._check_archivers()
        if mime not in self._options["archivers"]["extract"]:
            self._response[R_ERROR] = "Unable to extract files from archive"
            return

        arc = self._options["archivers"]["extract"][mime]

        cmd = [arc[ARCHIVE_CMD]]
        for arg in arc[ARCHIVE_ARGC].split():
            cmd.append(arg)
        cmd.append(os.path.basename(cur_file))

        target_dir = cur_dir
        added = None
        if makedir and makedir != "0":
            base_name = os.path.splitext(os.path.basename(cur_file))[0] or "New Folder"
            target_dir = os.path.join(target_dir, base_name)
            target_dir = _unique_name(target_dir, copy="")
            try:
                os.mkdir(target_dir, int(self._options["dir_mode"]))
            except OSError:
                self._response[R_ERROR] = "Unable to create folder: " + base_name
                return
            cmd += shlex.split(arc["argd"].format(shlex.quote(target_dir)))
            added = [self._info(target_dir)]

        if added is None:
            try:
                existing_files = os.listdir(cur_dir)
            except PermissionError:
                # FIXME: This will likely never happen.
                # The find helper will already have failed
                # to find the file without parent dir read access.
                self._response[R_ERROR] = "Access denied"
                return

        cur_cwd = os.getcwd()
        os.chdir(cur_dir)
        ret = _run_sub_process(cmd)
        os.chdir(cur_cwd)
        if not ret:
            self._response[R_ERROR] = "Unable to extract files from archive"
            return

        if added is None:
            added = [
                self._info(os.path.join(cur_dir, dname))
                for dname in os.listdir(cur_dir)
                if dname not in existing_files
            ]

        self._response[R_ADDED] = added

    def __ping(self) -> None:
        """Workaround for Safari."""
        self._http_status_code = 200
        self._http_header["Connection"] = "close"

    def __search(self) -> None:
        if API_Q not in self._request:
            self._response[R_ERROR] = "Invalid parameters"
            return

        if API_TARGET in self._request:
            target = self._request[API_TARGET]
            if not target:
                self._response[R_ERROR] = "Invalid parameters"
                return
            search_path = self._find_dir(target)
        else:
            search_path = self._options["root"]

        if not search_path:
            self._response[R_ERROR] = "File not found"
            return

        mimes = self._request.get(API_MIMES)

        result = []
        query = self._request[API_Q]
        for root, dirs, files in os.walk(search_path):
            for fil in files:
                if query.lower() in fil.lower():
                    file_path = os.path.join(root, fil)
                    if mimes is None:
                        result.append(self._info(file_path))
                    else:
                        if _mimetype(file_path) in mimes:
                            result.append(self._info(file_path))
            if mimes is None:
                for folder in dirs:
                    file_path = os.path.join(root, folder)
                    if query.lower() in folder.lower():
                        result.append(self._info(file_path))
        self._response[R_FILES] = result

    def _cwd(self, path: str) -> None:
        """Get Current Working Directory."""
        name = os.path.basename(path)
        if path == self._options["root"]:
            name = self._options["root_alias"]
            root = True
        else:
            root = False

        if self._options["root_alias"]:
            basename = self._options["root_alias"]
        else:
            basename = os.path.basename(self._options["root"])

        rel = os.path.join(basename, path[len(self._options["root"]) :])

        info = {
            "hash": self._hash(path),
            "name": self._check_utf8(name),
            "mime": "directory",
            "rel": self._check_utf8(rel),
            "size": 0,
            "date": datetime.fromtimestamp(os.stat(path).st_mtime).strftime(
                "%d %b %Y %H:%M"
            ),
            "read": 1,
            "write": 1 if self._is_allowed(path, "write") else 0,
            "locked": 0,
            "rm": not root and self._is_allowed(path, "rm"),
            "volumeid": self.volumeid,
        }

        try:
            info["dirs"] = 1 if any(next(os.walk(path))[1]) else 0
        except StopIteration:
            info["dirs"] = 0

        self._response[R_CWD] = info

    def _info(self, path: str) -> Info:
        # mime = ''
        filetype = "file"
        if os.path.isfile(path):
            filetype = "file"
        elif os.path.isdir(path):
            filetype = "dir"
        elif os.path.islink(path):
            filetype = "link"

        stat = os.lstat(path)
        readable = self._is_allowed(path, "read")
        writable = self._is_allowed(path, "write")
        deletable = self._is_allowed(path, "rm")

        info = {
            "name": self._check_utf8(os.path.basename(path)),
            "hash": self._hash(path),
            "mime": "directory" if filetype == "dir" else _mimetype(path),
            "read": 1 if readable else 0,
            "write": 1 if writable else 0,
            "locked": 1 if not readable and not writable and not deletable else 0,
            "ts": stat.st_mtime,
        }  # type: Info

        if self._options["expose_real_path"]:
            info["path"] = os.path.abspath(path)

        if filetype == "dir":
            info["volumeid"] = self.volumeid
            try:
                info["dirs"] = 1 if any(next(os.walk(path))[1]) else 0
            except StopIteration:
                info["dirs"] = 0

        if path != self._options["root"]:
            info["phash"] = self._hash(os.path.dirname(path))

        if filetype == "link":
            lpath = self._read_link(path)
            if not lpath:
                info["mime"] = "symlink-broken"
                return info

            if os.path.isdir(lpath):
                info["mime"] = "directory"
            else:
                info["mime"] = _mimetype(lpath)

            if self._options["root_alias"]:
                basename = self._options["root_alias"]
            else:
                basename = os.path.basename(self._options["root"])

            info["link"] = self._hash(lpath)
            info["alias"] = os.path.join(basename, lpath[len(self._options["root"]) :])
            info["read"] = 1 if info["read"] and self._is_allowed(lpath, "read") else 0
            info["write"] = (
                1 if info["write"] and self._is_allowed(lpath, "write") else 0
            )
            info["locked"] = (
                1
                if (
                    not info["write"]
                    and not info["read"]
                    and not self._is_allowed(lpath, "rm")
                )
                else 0
            )
            info["size"] = 0
        else:
            lpath = None
            info["size"] = self._dir_size(path) if filetype == "dir" else stat.st_size

        if not info["mime"] == "directory":
            if self._options["file_url"] and info["read"]:
                if lpath:
                    info["url"] = self._path2url(lpath)
                else:
                    info["url"] = self._path2url(path)
            if info["mime"][0:5] == "image":
                thumbs_dir = self._options["tmb_dir"]
                if self._can_create_tmb():
                    assert thumbs_dir  # typing
                    dim = self._get_img_size(path)
                    if dim:
                        info["dim"] = dim

                    # if we are in tmb dir, files are thumbs itself
                    if os.path.dirname(path) == thumbs_dir:
                        info["tmb"] = self._path2url(path)
                        return info

                    tmb = os.path.join(thumbs_dir, info["hash"] + ".png")

                    if os.path.exists(tmb):
                        tmb_url = self._path2url(tmb)
                        info["tmb"] = tmb_url
                    else:
                        if info["mime"].startswith("image/"):
                            info["tmb"] = "1"

        if info["mime"] == "application/x-empty" or info["mime"] == "inode/x-empty":
            info["mime"] = "text/plain"

        return info

    def _remove(self, target: str) -> bool:
        """Provide internal remove procedure."""
        if not self._is_allowed(target, "rm"):
            self._set_error_data(target, "Access denied")

        if not os.path.isdir(target):
            try:
                os.unlink(target)
                self._rm_tmb(target)
                return True
            except OSError:
                self._set_error_data(target, "Remove failed")
                return False
        else:
            try:
                targets = os.listdir(target)
            except PermissionError:
                self._set_error_data(target, "Access denied")
                return False

            for fil in targets:
                if self._is_accepted(fil):
                    self._remove(os.path.join(target, fil))
            try:
                os.rmdir(target)
                return True
            except OSError:
                self._set_error_data(target, "Remove failed")
                return False

    def _copy(self, src: str, dst: str) -> bool:
        """Provide internal copy procedure."""
        dst_dir = os.path.dirname(dst)
        if not (self._is_allowed(src, "read") and self._is_allowed(dst_dir, "write")):
            self._set_error_data(src, "Access denied")
            return False
        if os.path.exists(dst):
            self._set_error_data(
                dst, "File or folder with the same name already exists"
            )
            return False

        if not os.path.isdir(src):
            try:
                shutil.copyfile(src, dst)
                shutil.copymode(src, dst)
                return True
            except (shutil.SameFileError, OSError):
                self._set_error_data(src, "Unable to copy files")
                return False
        else:
            try:
                os.mkdir(dst, int(self._options["dir_mode"]))
                shutil.copymode(src, dst)
            except (shutil.SameFileError, OSError):
                self._set_error_data(src, "Unable to copy files")
                return False

            try:
                srcs = os.listdir(src)
            except PermissionError:
                self._set_error_data(src, "Access denied")
                return False

            for i in srcs:
                new_src = os.path.join(src, i)
                new_dst = os.path.join(dst, i)
                if not self._copy(new_src, new_dst):
                    self._set_error_data(new_src, "Unable to copy files")
                    return False

        return True

    def _find_dir(self, fhash: str, path: Optional[str] = None) -> Optional[str]:
        """Find directory by hash."""
        fhash = str(fhash)
        # try to get find it in the cache
        cached_path = self._cached_path.get(fhash)
        if cached_path:
            return cached_path

        if not path:
            path = self._options["root"]
            if fhash == self._hash(path):
                return path

        if not os.path.isdir(path):
            return None

        for root, dirs, _ in os.walk(path, topdown=True):
            for folder in dirs:
                folder_path = os.path.join(root, folder)
                if not os.path.islink(folder_path) and fhash == self._hash(folder_path):
                    return folder_path
        return None

    def _find(self, fhash: str, parent: Optional[str] = None) -> Optional[str]:
        """Find file/dir by hash."""
        fhash = str(fhash)
        cached_path = self._cached_path.get(fhash)
        if cached_path:
            return cached_path
        if not parent:
            parent = self._options["root"]
        if os.path.isdir(parent):
            for root, dirs, files in os.walk(parent, topdown=True):
                for folder in dirs:
                    folder_path = os.path.join(root, folder)
                    if fhash == self._hash(folder_path):
                        return folder_path
                for fil in files:
                    file_path = os.path.join(root, fil)
                    if fhash == self._hash(file_path):
                        return file_path

        return None

    def _tmb(self, path: str, tmb_path: str) -> bool:
        """Provide internal thumbnail create procedure."""
        try:
            img = self._img.open(path).copy()  # type: ignore
            size = self._options["tmb_size"], self._options["tmb_size"]
            box = _crop_tuple(img.size)
            if box:
                img = img.crop(box)
            img.thumbnail(size, self._img.ANTIALIAS)  # type: ignore
            img.save(tmb_path, "PNG")
        # UnidentifiedImageError requires Pillow 7.0.0
        except (OSError, ValueError) as exc:
            self._debug("tmbFailed_" + path, str(exc))
            return False
        return True

    def _rm_tmb(self, path: str) -> None:
        tmb = self._tmb_path(path)
        if tmb:
            if os.path.exists(tmb):
                try:
                    os.unlink(tmb)
                except OSError:
                    pass

    def _read_link(self, path: str) -> Optional[str]:
        """Read link and return real path if not broken."""
        target = os.readlink(path)
        if not target[0] == "/":
            target = os.path.join(os.path.dirname(path), target)
        target = os.path.normpath(target)
        if os.path.exists(target):
            # The external link could not be found
            # author: wangyx64
            # date:  2022/5/25
            # if not target.find(self._options["root"]) == -1:
            return target
        return None

    def _dir_size(self, path: str) -> int:
        total_size = 0
        if self._options["dir_size"]:
            for dirpath, _, filenames in os.walk(path):
                for fil in filenames:
                    file_path = os.path.join(dirpath, fil)
                    if os.path.exists(file_path):
                        total_size += os.stat(file_path).st_size
        else:
            total_size = os.lstat(path).st_size
        return total_size

    def _fbuffer(
        self, fil: BinaryIO, chunk_size: int = _options["upload_write_chunk"]
    ) -> Generator[bytes, None, None]:
        # pylint: disable=no-self-use
        while True:
            chunk = fil.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def _can_create_tmb(self, path: Optional[str] = None) -> bool:
        if self._options["img_lib"] and self._options["tmb_dir"]:
            if path is not None:
                mime = _mimetype(path)
                if mime[0:5] != "image":
                    return False
            return True
        return False

    def _tmb_path(self, path: str) -> Optional[str]:
        tmb = None
        thumbs_dir = self._options["tmb_dir"]
        if thumbs_dir:
            if not os.path.dirname(path) == thumbs_dir:
                tmb = os.path.join(thumbs_dir, self._hash(path) + ".png")
        return tmb

    def _is_upload_allow(self, name: str) -> bool:
        allow = False
        deny = False
        mime = _mimetype(name)

        if "all" in self._options["upload_allow"]:
            allow = True
        else:
            for opt in self._options["upload_allow"]:
                if mime.find(opt) == 0:
                    allow = True

        if "all" in self._options["upload_deny"]:
            deny = True
        else:
            for opt in self._options["upload_deny"]:
                if mime.find(opt) == 0:
                    deny = True

        if self._options["upload_order"][0] == "allow":  # ,deny
            if deny is True:
                return False
            return bool(allow)
        # deny,allow
        if allow is True:
            return True
        if deny is True:
            return False
        return True

    def _is_accepted(self, target: str) -> bool:
        if target in (".", ".."):
            return False
        if target[0:1] == "." and not self._options["dot_files"]:
            return False
        return True

    def _is_allowed(self, path: str, access: str) -> bool:
        if not os.path.exists(path):
            return False

        if access == "read":
            if not os.access(path, os.R_OK):
                self._set_error_data(path, access)
                return False
        elif access == "write":
            if not os.access(path, os.W_OK):
                self._set_error_data(path, access)
                return False
        elif access == "rm":
            if not os.access(os.path.dirname(path), os.W_OK):
                self._set_error_data(path, access)
                return False
        else:
            return False

        path = path[len(os.path.normpath(self._options["root"])) :]
        for ppath, permissions in self._options["perms"].items():
            regex = r"" + ppath
            if re.search(regex, path) and access in permissions:
                return permissions[access]

        return self._options["defaults"][access]

    def _hash(self, path: str) -> str:
        """Hash of the path."""
        hash_code = make_hash(path)

        # TODO: what if the cache getting to big?  # pylint: disable=fixme
        self._cached_path[hash_code] = path
        return hash_code

    def _path2url(self, path: str) -> str:
        cur_dir = path
        length = len(self._options["root"])
        url = multi_urljoin(
            self._options["base_url"], self._options["files_url"], cur_dir[length:],
        )
        url = self._check_utf8(url).replace(os.sep, "/")
        url = quote(url, safe="/")
        return url

    def _set_error_data(self, path: str, msg: str) -> None:
        """Collect error/warning messages."""
        self._error_data[path] = msg

    def _init_img_lib(self) -> Optional[str]:
        if not self._options["img_lib"] or self._options["img_lib"] == "auto":
            self._options["img_lib"] = "PIL"

        if self._options["img_lib"] == "PIL":
            try:
                from PIL import \
                    Image  # pylint: disable=import-outside-toplevel

                self._img = Image
            except ImportError:
                self._img = None
                self._options["img_lib"] = None
        else:
            raise NotImplementedError

        self._debug("img_lib", self._options["img_lib"])
        return self._options["img_lib"]

    def _get_img_size(self, path: str) -> Optional[str]:
        if not self._init_img_lib():
            return None
        if self._can_create_tmb():
            try:
                img = self._img.open(path)  # type: ignore
                return str(img.size[0]) + "x" + str(img.size[1])
            except OSError:  # UnidentifiedImageError requires Pillow 7.0.0
                print("WARNING: unidentified image or file not found: " + path)

        return None

    def _debug(self, key: str, val: Any) -> None:
        if self._options["debug"]:
            self._response[R_DEBUG].update({key: val})

    def _check_archivers(self) -> None:
        # import subprocess
        # proc = subprocess.Popen(['tar', '--version'], shell = False,
        # stdout = subprocess.PIPE, stderr=subprocess.PIPE)
        # out, err = proc.communicate()
        # print 'out:', out, '\nerr:', err, '\n'
        archive = {"create": {}, "extract": {}}  # type: Archivers

        if (
            "archive" in self._options["disabled"]
            and "extract" in self._options["disabled"]
        ):
            self._options["archive_mimes"] = []
            self._options["archivers"] = archive
            return

        tar = _run_sub_process(["tar", "--version"])
        gzip = _run_sub_process(["gzip", "--version"])
        bzip2 = _run_sub_process(["bzip2", "--version"])
        zipc = _run_sub_process(["zip", "--version"])
        unzip = _run_sub_process(["unzip", "--help"])
        rar = _run_sub_process(["rar", "--version"], valid_return=[0, 7])
        unrar = _run_sub_process(["unrar"], valid_return=[0, 7])
        p7z = _run_sub_process(["7z", "--help"])
        p7za = _run_sub_process(["7za", "--help"])
        p7zr = _run_sub_process(["7zr", "--help"])

        # tar = False
        # tar = gzip = bzip2 = zipc = unzip = rar = unrar = False
        # print tar, gzip, bzip2, zipc, unzip, rar, unrar, p7z, p7za, p7zr

        create = archive["create"]
        extract = archive["extract"]

        if tar:
            mime = "application/x-tar"
            create.update(
                {mime: {ARCHIVE_CMD: "tar", ARCHIVE_ARGC: "-cf", ARCHIVE_EXT: "tar"}}
            )
            extract.update(
                {
                    mime: {
                        ARCHIVE_CMD: "tar",
                        ARCHIVE_ARGC: "-xf",
                        ARCHIVE_EXT: "tar",
                        "argd": "-C {}",
                    }
                }
            )

        if tar and gzip:
            mime = "application/x-gzip"
            create.update(
                {
                    mime: {
                        ARCHIVE_CMD: "tar",
                        ARCHIVE_ARGC: "-czf",
                        ARCHIVE_EXT: "tar.gz",
                    }
                }
            )
            extract.update(
                {
                    mime: {
                        ARCHIVE_CMD: "tar",
                        ARCHIVE_ARGC: "-xzf",
                        ARCHIVE_EXT: "tar.gz",
                        "argd": "-C {}",
                    }
                }
            )

        if tar and bzip2:
            mime = "application/x-bzip2"
            create.update(
                {
                    mime: {
                        ARCHIVE_CMD: "tar",
                        ARCHIVE_ARGC: "-cjf",
                        ARCHIVE_EXT: "tar.bz2",
                    }
                }
            )
            extract.update(
                {
                    mime: {
                        ARCHIVE_CMD: "tar",
                        ARCHIVE_ARGC: "-xjf",
                        ARCHIVE_EXT: "tar.bz2",
                        "argd": "-C {}",
                    }
                }
            )

        mime = "application/zip"
        if zipc:
            create.update(
                {mime: {ARCHIVE_CMD: "zip", ARCHIVE_ARGC: "-r9", ARCHIVE_EXT: "zip"}}
            )
        if unzip:
            extract.update(
                {
                    mime: {
                        ARCHIVE_CMD: "unzip",
                        ARCHIVE_ARGC: "",
                        ARCHIVE_EXT: "zip",
                        "argd": "-d {}",
                    }
                }
            )

        mime = "application/x-rar"
        if rar:
            create.update(
                {
                    mime: {
                        ARCHIVE_CMD: "rar",
                        ARCHIVE_ARGC: "a -inul",
                        ARCHIVE_EXT: "rar",
                    }
                }
            )
            extract.update(
                {
                    mime: {
                        ARCHIVE_CMD: "rar",
                        ARCHIVE_ARGC: "x -y",
                        ARCHIVE_EXT: "rar",
                        "argd": "{}",
                    }
                }
            )
        elif unrar:
            extract.update(
                {
                    mime: {
                        ARCHIVE_CMD: "unrar",
                        ARCHIVE_ARGC: "x -y",
                        ARCHIVE_EXT: "rar",
                        "argd": "{}",
                    }
                }
            )

        p7zip = None
        if p7z:
            p7zip = "7z"
        elif p7za:
            p7zip = "7za"
        elif p7zr:
            p7zip = "7zr"

        if p7zip:
            mime = "application/x-7z-compressed"
            create.update(
                {mime: {ARCHIVE_CMD: p7zip, ARCHIVE_ARGC: "a -t7z", ARCHIVE_EXT: "7z"}}
            )
            extract.update(
                {
                    mime: {
                        ARCHIVE_CMD: p7zip,
                        ARCHIVE_ARGC: "extract -y",
                        ARCHIVE_EXT: "7z",
                        "argd": "-o{}",
                    }
                }
            )

            mime = "application/x-tar"
            if mime not in create:
                create.update(
                    {
                        mime: {
                            ARCHIVE_CMD: p7zip,
                            ARCHIVE_ARGC: "a -ttar",
                            ARCHIVE_EXT: "tar",
                        }
                    }
                )
            if mime not in extract:
                extract.update(
                    {
                        mime: {
                            ARCHIVE_CMD: p7zip,
                            ARCHIVE_ARGC: "extract -y",
                            ARCHIVE_EXT: "tar",
                            "argd": "-o{}",
                        }
                    }
                )

            mime = "application/x-gzip"
            if mime not in create:
                create.update(
                    {
                        mime: {
                            ARCHIVE_CMD: p7zip,
                            ARCHIVE_ARGC: "a -tgzip",
                            ARCHIVE_EXT: "gz",
                        }
                    }
                )
            if mime not in extract:
                extract.update(
                    {
                        mime: {
                            ARCHIVE_CMD: p7zip,
                            ARCHIVE_ARGC: "extract -y",
                            ARCHIVE_EXT: "tar.gz",
                            "argd": "-o{}",
                        }
                    }
                )

            mime = "application/x-bzip2"
            if mime not in create:
                create.update(
                    {
                        mime: {
                            ARCHIVE_CMD: p7zip,
                            ARCHIVE_ARGC: "a -tbzip2",
                            ARCHIVE_EXT: "bz2",
                        }
                    }
                )
            if mime not in extract:
                extract.update(
                    {
                        mime: {
                            ARCHIVE_CMD: p7zip,
                            ARCHIVE_ARGC: "extract -y",
                            ARCHIVE_EXT: "tar.bz2",
                            "argd": "-o{}",
                        }
                    }
                )

            mime = "application/zip"
            if mime not in create:
                create.update(
                    {
                        mime: {
                            ARCHIVE_CMD: p7zip,
                            ARCHIVE_ARGC: "a -tzip",
                            ARCHIVE_EXT: "zip",
                        }
                    }
                )
            if mime not in extract:
                extract.update(
                    {
                        mime: {
                            ARCHIVE_CMD: p7zip,
                            ARCHIVE_ARGC: "extract -y",
                            ARCHIVE_EXT: "zip",
                            "argd": "-o{}",
                        }
                    }
                )

        if not self._options["archive_mimes"]:
            self._options["archive_mimes"] = list(create.keys())
        else:
            pass
        self._options["archivers"] = archive

    def _check_utf8(self, name: Union[str, bytes]) -> str:
        if isinstance(name, str):
            return name
        try:
            str_name = name.decode("utf-8")
        except UnicodeDecodeError:
            str_name = str(name, "utf-8", "replace")
            self._debug("invalid encoding", str_name)
        return str_name


def _check_name(filename: str) -> bool:
    """Check for valid file name."""
    if sanitize_filename(filename) != filename:
        return False
    return True


def _check_dir(filepath: str) -> bool:
    """Check for valid dir name."""
    if sanitize_filepath(filepath) != filepath:
        return False
    return True


def _mimetype(path: str) -> str:
    """Detect mimetype of file."""
    mime = mimetypes.guess_type(path)[0] or "unknown"
    _, ext = os.path.splitext(path)

    # Modify the function to distinguish compressed file types
    # author: wangwd11
    # date:  2021/3/23
    if mime == "application/x-tar" and mimetypes.guess_type(path)[1] == "gzip":
        mime = "application/x-gzip"
    # Change ended.

    if mime == "unknown" and ext in mimetypes.types_map:
        mime = mimetypes.types_map[ext]

    if mime == "text/plain" and ext == ".pl":
        mime = MIME_TYPES[ext]

    if mime == "application/vnd.ms-office" and ext == ".doc":
        mime = MIME_TYPES[ext]

    if mime == "unknown":
        if os.path.basename(path) in ["README", "ChangeLog", "LICENSE", "Makefile"]:
            mime = "text/plain"
        else:
            if ext in MIME_TYPES:
                mime = MIME_TYPES[ext]
            else:
                mime = "text/plain"
    return mime


def _unique_name(path: str, copy: str = " copy") -> str:
    """Generate unique name for file copied file."""

    # Modify the function to support non path parameters
    # author: wangwd11
    # date:  2021/1/29

    if path == os.path.basename(path):
        import uuid
        return f'.{uuid.uuid4()}-{path}'

    # Change ended.

    cur_dir = os.path.dirname(path)
    cur_name = os.path.basename(path)
    last_dot = cur_name.rfind(".")
    ext = new_name = ""

    if not os.path.isdir(path) and re.search(r"\..{3}\.(gz|bz|bz2)$", cur_name):
        pos = -7
        if cur_name[-1:] == "2":
            pos -= 1
        ext = cur_name[pos:]
        old_name = cur_name[0:pos]
        new_name = old_name + copy
    elif os.path.isdir(path) or last_dot <= 0:
        old_name = cur_name
        new_name = old_name + copy
    else:
        ext = cur_name[last_dot:]
        old_name = cur_name[0:last_dot]
        new_name = old_name + copy

    pos = 0

    if old_name[-len(copy) :] == copy:
        new_name = old_name
    elif re.search(r"" + copy + r"\s\d+$", old_name):
        pos = old_name.rfind(copy) + len(copy)
        new_name = old_name[0:pos]
    else:
        new_path = os.path.join(cur_dir, new_name + ext)
        if not os.path.exists(new_path):
            return new_path

    # if we are here then copy already exists or making copy of copy
    # we will make new indexed copy *black magic*
    idx = 1
    if pos > 0:
        # fix [BUG-225319]
        # date: 2021/2/7
        idx = int(old_name[pos:]) if old_name[pos:] else idx
        # Change ended.
    while True:
        idx += 1
        new_name_ext = new_name + " " + str(idx) + ext
        new_path = os.path.join(cur_dir, new_name_ext)
        if not os.path.exists(new_path):
            return new_path
        # if idx >= 1000: break # possible loop


def _run_sub_process(cmd: List[str], valid_return: Optional[List[int]] = None) -> bool:
    if valid_return is None:
        valid_return = [0]
    try:
        completed = subprocess.run(
            cmd, input=b"", check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except (subprocess.SubprocessError, OSError):
        return False

    if completed.returncode not in valid_return:
        print(str(completed.stderr))
        return False

    return True


def _crop_tuple(size: Tuple[int, int]) -> Optional[Tuple[int, int, int, int]]:
    """Return the crop rectangle, as a (left, upper, right, lower)-tuple."""
    width, height = size
    if width > height:  # landscape
        left = int((width - height) / 2)
        upper = 0
        right = left + height
        lower = height
        return (left, upper, right, lower)
    if height > width:  # portrait
        left = 0
        upper = int((height - width) / 2)
        right = width
        lower = upper + width
        return (left, upper, right, lower)

    # cube
    return None


def make_hash(to_hash: str) -> str:
    # The MD5 encrypted path cannot be reversed
    # author: wangyx64
    # date:  2022/5/30
    """Return a hash of to_hash."""
    # hash_obj = hashlib.md5()
    # hash_obj.update(to_hash.encode("utf-8"))
    # hash_code = str(hash_obj.hexdigest())
    hash_code = base64.b16encode(
        to_hash.encode('utf-8')
    ).decode()
    return hash_code


def multi_urljoin(*parts: str) -> str:
    """Join multiple url parts into a valid url."""
    if parts[0].startswith("http"):
        return str(urljoin(parts[0], "/".join(part.strip("/") for part in parts[1:]),))
    return "/" + "/".join(part.strip("/") for part in parts if part)
