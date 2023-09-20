# -*- coding: utf-8 -*-
# Copyright 2015-present Lenovo
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

import base64
import logging
import os
import os.path
import re
import shutil

from .imjoy_elfinder.api_const import (
    API_CONTENT, API_DST, API_INIT, API_NAME, API_TARGET, API_TARGETS,
    API_TREE, ARCHIVE_EXT, R_ADDED, R_API, R_CHANGED, R_CWD, R_ERROR, R_FILES,
    R_NETDRIVERS, R_OPTIONS, R_OPTIONS_ARCHIVERS, R_OPTIONS_COPY_OVERWRITE,
    R_OPTIONS_CREATE, R_OPTIONS_CREATE_EXT, R_OPTIONS_DISABLED,
    R_OPTIONS_DISP_INLINE_REGEX, R_OPTIONS_EXTRACT, R_OPTIONS_I18N_FOLDER_NAME,
    R_OPTIONS_JPG_QUALITY, R_OPTIONS_MIME_ALLOW, R_OPTIONS_MIME_DENY,
    R_OPTIONS_MIME_FIRST_ORDER, R_OPTIONS_PATH, R_OPTIONS_SEPARATOR,
    R_OPTIONS_SYNC_CHK_AS_TS, R_OPTIONS_SYNC_MIN_MS, R_OPTIONS_UI_CMD_MAP,
    R_OPTIONS_UPLOAD_MAX_CONN, R_OPTIONS_UPLOAD_MAX_SIZE,
    R_OPTIONS_UPLOAD_MIME, R_OPTIONS_UPLOAD_OVERWRITE, R_TREE, R_UPLMAXFILE,
    R_UPLMAXSIZE,
)
from .imjoy_elfinder.elfinder import (
    COMMANDS, Connector, _check_name, _mimetype,
)

logger = logging.getLogger(__name__)

COMMANDS.update({
    "hash": "__hash",
    "preview": "__preview",
})


class FilesConnector(Connector):
    Connector._options["root_alias"] = "MyFolder"
    Connector._options["disabled"] = ["netmount"]

    @property
    def valid_path_pattern(self):
        root = os.path.normpath(self._options["root"])
        return re.compile(
            f'^{root}(?:$|/)'
            r'(?!(.*/)?\.\.(?:$|/))'
            r'[^\r\n]*$'
        )

    def __init__(
            self, user, adapter, base_url="",
            upload_max_size=5 * 1024 * 1024 * 1024,  # 5GB
            tmb_dir=".tmb", expose_real_path=True,
            dot_files=False, debug=False
    ):
        self.user = user
        self.adapter = adapter
        super().__init__(
            self.user.workspace, self.user.workspace, base_url,
            upload_max_size, tmb_dir, expose_real_path,
            dot_files, debug
        )

    def run(self, http_request):
        """Run main function."""
        super().run(http_request)
        self._handle_rep_added()
        self._handle_rep_cwd()
        return self._http_status_code, self._http_header, self._response

    def __getattr__(self, item_key):
        if item_key.startswith('_FilesConnector'):
            new_item_key = item_key.replace('_FilesConnector', '_Connector')
            return getattr(self, new_item_key)
        raise KeyError('FilesConnector.__getattr__:' + item_key)

    def _handle_rep_added(self):
        """handle response added."""
        path_list = self._response.get(R_ADDED)
        if path_list:
            self._response[R_ADDED] = []
            for path_dict in path_list:
                path_hash = path_dict["hash"]
                path = self._find(path_hash)
                self.adapter.change_owner(path, self.user)
                self._response[R_ADDED].append(self._info(path))

    def _handle_rep_cwd(self):
        """handle response cwd."""
        cwd = self._response.get(R_CWD)
        if cwd:
            path = self._find(cwd["hash"])
            if path == self._options["root"]:
                cwd["option"] = self._r_option(path)
                cwd["phash"] = ""
            else:
                cwd["phash"] = self._hash(os.path.dirname(path))

    def _is_allowed(self, path: str, access: str) -> bool:
        """ Determine the file permissions."""
        if not os.path.lexists(path):
            return False

        if access == "read":
            if not self.adapter.is_readable(path=path, user=self.user):
                self._set_error_data(path, access)
                return False
        elif access == "write":
            if not self.adapter.is_writable(path=path, user=self.user):
                self._set_error_data(path, access)
                return False
        elif access == "rm":
            if not self.adapter.is_writable(
                    path=os.path.dirname(path), user=self.user
            ):
                self._set_error_data(path, access)
                return False
        else:
            return False
        return self._options["defaults"][access]

    def _change_owner(self, path, followlinks=False):
        self.adapter.change_owner(path, self.user, followlinks)

    def _copy(self, src: str, dst: str) -> bool:
        """Provide internal copy procedure."""
        dst_dir = os.path.dirname(dst)
        if not (self._is_allowed(src, "read") and
                self._is_allowed(dst_dir, "write")):
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
                self._change_owner(dst)
                return True
            except (shutil.SameFileError, OSError):
                self._set_error_data(src, "Unable to copy files")
                return False
        else:
            self._copy_dir(src, dst)
        return True

    def _copy_dir(self, src: str, dst: str):
        try:
            os.mkdir(dst, int(self._options["dir_mode"]))
            shutil.copymode(src, dst)
            self._change_owner(dst)
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

    def _r_option(self, path):
        resp_option = {
            R_OPTIONS_PATH: path,
            R_OPTIONS_SEPARATOR: os.path.sep,
            R_OPTIONS_DISABLED: self._options["disabled"],
            R_OPTIONS_ARCHIVERS: {
                R_OPTIONS_CREATE: list(
                    self._options["archivers"]["create"].keys()
                ),
                R_OPTIONS_EXTRACT: list(
                    self._options["archivers"]["extract"].keys()
                ),
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
            R_OPTIONS_DISP_INLINE_REGEX:
                "^(?:(?:image|video|audio)|application/"
                + "(?:x-mpegURL|dash\\+xml)|(?:text/plain|application/pdf)$)",
            R_OPTIONS_JPG_QUALITY: 100,
            R_OPTIONS_SYNC_CHK_AS_TS: 1,
            R_OPTIONS_SYNC_MIN_MS: 30000,
            R_OPTIONS_UI_CMD_MAP: {},
        }
        if path == self._options["root"]:
            resp_option.update({"csscls": "elfinder-navbar-root-custom"})
        return resp_option

    def _info(self, path: str):
        info = super()._info(path)
        if path == self._options["root"]:
            r_opt = self._r_option(path)
            info.update(
                dict(
                    name=self._options["root_alias"],
                    isroot=1,
                    options=r_opt,
                    phash=""
                ))
        return info

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
        self._check_archivers()
        self._cwd(path)
        files = self._file(path)
        if path != self._options["root"] and init:
            files.extend(self._file(self._options["root"]))
        self._response[R_FILES] = files
        self._handle_open_tree(path)
        self._response[R_NETDRIVERS] = []
        self._response[R_UPLMAXFILE] = 1000
        self._response[R_UPLMAXSIZE] = (
                str(self._options["upload_max_size"] / (1024 * 1024)) + "M"
        )
        self._response[R_OPTIONS] = self._r_option(path)

    def _file(self, path):
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
        return files

    def _handle_open_tree(self, path):
        if self._request.get(API_TREE):
            if path != self._options["root"]:
                self._response[R_FILES].append(self._info(path))
                self._response[R_FILES].append(
                    self._info(self._options["root"])
                )
            else:
                self._response[R_FILES].append(self._info(path))
        if not self._request.get(API_TREE) and path != self._options["root"]:
            self._response[R_FILES].append(self._info(self._options["root"]))

    def _tree(self, path, include_self=True) -> None:
        """Return directory tree starting from path."""
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
        tree = []
        if include_self:
            tree.append(self._info(path))
        try:
            directories = os.listdir(path)
        except PermissionError:
            self._response[R_ERROR] = "Access denied"
            return
        for directory in sorted(directories):
            dir_path = os.path.join(path, directory)
            if (
                    os.path.isdir(dir_path)
                    and not os.path.islink(dir_path)
                    and self._is_accepted(directory)
            ):
                tree.append(self._info(dir_path))
        return tree

    def __parents(self) -> None:
        """Return sub-tree to the current path, including current path"""
        target = self._request.get(API_TARGET)
        if not target:
            self._response[R_ERROR] = "Invalid parameters"
            return
        path = self._find_dir(target)
        if path is None:
            self._response[R_ERROR] = "Directory not found"
            return
        if not self._is_allowed(path, "read"):
            self._response[R_ERROR] = "Access denied"
            return
        if os.path.abspath(path) == os.path.abspath(self._options["root"]):
            self._response[R_TREE] = [self._info(path)]
            return
        dirs = []
        while True:
            parent = os.path.dirname(path)
            sub_dirs = self._tree(parent)
            dirs.extend(sub_dirs)
            if parent == os.path.abspath(self._options["root"]):
                break
            else:
                path = parent
        self._response[R_TREE] = dirs

    def __hash(self):
        path = self._request.get(API_TARGET)
        if not path or self.valid_path_pattern.match(path) is None:
            self._response[R_ERROR] = "Invalid parameters"
            return
        self._response = {
            'hash': self._hash(path),
            'exists': os.path.exists(path),
            'isdir': os.path.isdir(path)
        }

    def __preview(self) -> None:
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

        with open(cur_file, "rb") as f:
            self._response['data'] = base64.b64encode(f.read()).decode()
            self._response['type'] = os.path.splitext(cur_file)[-1]

    # flake8: noqa: C901
    def _find_dir(self, fhash, path=None):
        """Find directory by hash."""
        fhash = str(fhash)
        # try to get find it in the cache
        cached_path = self._cached_path.get(fhash)
        if cached_path:
            return cached_path

        try:
            decode_path = base64.b16decode(fhash.encode()).decode()
        except Exception:
            decode_path = None
        if decode_path:
            if self.valid_path_pattern.match(decode_path) is None:
                return None
            return decode_path

        if not path:
            path = self._options["root"]
            if fhash == self._hash(path):
                return path

        if self.valid_path_pattern.match(path) is None or not os.path.isdir(path):
            return None

        for root, dirs, _ in os.walk(path, topdown=True, followlinks=True):
            for folder in dirs:
                folder_path = os.path.join(root, folder)
                if fhash == self._hash(folder_path):
                    return folder_path
        return None

    def __put(self) -> None:
        """Save content in file."""
        target = self._request.get(API_TARGET)
        content = self._request.get(API_CONTENT)
        if not target:
            self._response[R_ERROR] = "Invalid parameters"
            return
        cur_file = self._find(target)
        if not cur_file:
            self._response[R_ERROR] = "File not found"
            return
        if not self._is_allowed(cur_file, "write"):
            self._response[R_ERROR] = "Access denied"
            return
        if not content:
            try:
                with open(cur_file, "w+") as text_fil:
                    text_fil.write(self._request[API_CONTENT])
                self._response[R_CHANGED] = [self._info(cur_file)]
            except OSError:
                self._response[R_ERROR] = "Unable to write to file"
        else:
            super()._Connector__put()

    def _remove(self, target: str) -> bool:
        """Provide internal remove procedure."""
        self._dot_files_cache = self._options["dot_files"]
        self._options["dot_files"] = True

        if not self._is_allowed(target, "rm"):
            self._set_error_data(target, "Access denied")
            return False

        if os.path.islink(target):
            try:
                os.unlink(target)
                return True
            except OSError:
                self._set_error_data(target, "Remove failed")
                return False
        ret = super()._remove(target)
        self._options["dot_files"] = self._dot_files_cache
        return ret

    def _check_archivers(self) -> None:
        super()._check_archivers()
        archive_mimes = set(self._options["archive_mimes"])
        archive_mimes.intersection_update(
            {"application/x-tar",
             "application/x-gzip",
             "application/zip"}
        )
        self._options["archive_mimes"] = list(archive_mimes)

        self._options["archivers"] = {"create": {}, "extract": {}}
        create = self._options["archivers"]["create"]
        extract = self._options["archivers"]["extract"]
        if "application/x-tar" in archive_mimes:
            create['application/x-tar'] = \
                {'cmd': 'tar', 'argc': '-cf', 'ext': 'tar'}
            extract['application/x-tar'] = \
                {
                    'cmd': 'tar', 'argc': '-xf',
                    'ext': 'tar', 'argd': '--overwrite -C {}'
                }
        if "application/x-gzip" in archive_mimes:
            create['application/x-gzip'] = \
                {'cmd': 'tar', 'argc': '-czf', 'ext': 'tgz'}
            extract['application/x-gzip'] = \
                {
                    'cmd': 'tar', 'argc': '-xzf',
                    'ext': 'tgz', 'argd': '--overwrite -C {}'
                }
        if "application/zip" in archive_mimes:
            create['application/zip'] = \
                {'cmd': 'zip', 'argc': '-r9', 'ext': 'zip'}
            extract['application/zip'] = \
                {
                    'cmd': 'unzip', 'argc': '-o',
                    'ext': 'zip', 'argd': '-d {}'
                }

    def __archive(self) -> None:
        """Compress files/directories to archive."""
        super()._Connector__archive()
        name = self._request.get(API_NAME)
        if name:
            name = self._check_utf8(name)
            adds = self._response.get(R_ADDED)
            if _check_name(name) and adds:
                path = self._find(adds[0]['hash'])
                if path is not None:
                    new_file = os.path.join(os.path.dirname(path), name)
                    try:
                        os.rename(path, new_file)
                    except OSError:
                        os.unlink(path)
                        self._response[R_ADDED] = []
                        self._response[R_ERROR] = "Unable to create archive"
                        return
                    self._response[R_ADDED] = [self._info(new_file)]

    def __paste(self) -> None:
        """Copy or cut files/directories."""
        if API_TARGETS in self._request and API_DST in self._request:
            dst = self._find_dir(self._request[API_DST])
            cur_dir = dst
            if not cur_dir or not dst or API_TARGETS not in self._request:
                self._response[R_ERROR] = "Invalid parameters"
                return
            files = self._request[API_TARGETS]

            if not self._is_allowed(dst, "write"):
                self._response[R_ERROR] = "Access denied"
                return

            for fhash in files:
                fil = self._find(fhash)
                if not fil:
                    self._response[R_ERROR] = "File not found"
                    return
                new_dst = os.path.join(dst, os.path.basename(fil))
                if os.path.exists(new_dst):
                    self._remove(new_dst)
        super()._Connector__paste()

    def __extract(self) -> None:
        super()._Connector__extract()
        path_list = self._response.get(R_ADDED)
        if path_list:
            for each_path in path_list:
                path_hash = each_path["hash"]
                path = self._find(path_hash)
                self.adapter.change_owner(path, self.user)
                for path, dirs, files in os.walk(path):
                    self.adapter.change_owner(path, self.user)
                    for name in files:
                        self.adapter.change_owner(
                            os.path.join(path, name), self.user
                        )

    # flake8: noqa: C901
    def _find(self, fhash, parent=None):
        """Find file/dir by hash."""
        fhash = str(fhash)
        cached_path = self._cached_path.get(fhash)
        if cached_path:
            return cached_path
        try:
            decode_path = base64.b16decode(fhash.encode()).decode()
        except Exception:
            decode_path = None
        if decode_path:
            if self.valid_path_pattern.match(decode_path) is None:
                return None
            return decode_path

        if not parent:
            parent = self._options["root"]
            if fhash == self._hash(parent):
                return parent

        if self.valid_path_pattern.match(path) is None or os.path.isdir(parent):
            for root, dirs, files in os.walk(
                    parent, topdown=True, followlinks=True
            ):
                for folder in dirs:
                    folder_path = os.path.join(root, folder)
                    if fhash == self._hash(folder_path):
                        return folder_path
                for fil in files:
                    file_path = os.path.join(root, fil)
                    if fhash == self._hash(file_path):
                        return file_path
        return None

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
                content = base64.b64encode(bin_fil.read()).decode(
                    "ascii"
                )
                mime_type = _mimetype(cur_file)
                self._response[API_CONTENT] = \
                    f"data:{mime_type};base64,{content}"
