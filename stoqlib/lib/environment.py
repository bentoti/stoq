# -*- coding: utf-8 -*-
# vi:si:et:sw=4:sts=4:ts=4

##
## Copyright (C) 2013 Async Open Source
##
## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU Lesser General Public License
## as published by the Free Software Foundation; either version 2
## of the License, or (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
##
## You should have received a copy of the GNU Lesser General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., or visit: http://www.gnu.org/.
##
##
## Author(s): Stoq Team <stoq-devel@async.com.br>
##

""" Environment variables """

import locale
import os


def is_developer_mode():
    if os.environ.get('STOQ_DEVELOPER_MODE') == '0':
        return

    from stoqlib.lib.kiwilibrary import library
    return library.uninstalled


def configure_locale(lang=None):
    if lang is None:
        lang = locale.getlocale()[0] or locale.getdefaultlocale()[0] or 'en_US'

    lang += '.UTF-8'
    os.environ['LC_ALL'] = lang
    os.environ['LANG'] = lang
    os.environ['LANGUAGE'] = lang
    # This will reset the locale to the ones defined in the environment
    locale.setlocale(locale.LC_ALL, '')

    locale.getpreferredencoding(True)
