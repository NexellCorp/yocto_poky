# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Fetch' implementations

Classes for obtaining upstream sources for the
BitBake build tools.

"""

# Copyright (C) 2003, 2004  Chris Larson
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#Based on functions from the base bb module, Copyright 2003 Holger Schurig
#

import os
import logging
import bb
from   bb import data
from bb.fetch import Fetch, FetchError, MissingParameterError, logger

class Cvs(Fetch):
    """
    Class to fetch a module or modules from cvs repositories
    """
    def supports(self, url, ud, d):
        """
        Check to see if a given url can be fetched with cvs.
        """
        return ud.type in ['cvs']

    def localpath(self, url, ud, d):
        if not "module" in ud.parm:
            raise MissingParameterError("cvs method needs a 'module' parameter")
        ud.module = ud.parm["module"]

        ud.tag = ud.parm.get('tag', "")

        # Override the default date in certain cases
        if 'date' in ud.parm:
            ud.date = ud.parm['date']
        elif ud.tag:
            ud.date = ""

        norecurse = ''
        if 'norecurse' in ud.parm:
            norecurse = '_norecurse'

        fullpath = ''
        if 'fullpath' in ud.parm:
            fullpath = '_fullpath'

        ud.localfile = data.expand('%s_%s_%s_%s%s%s.tar.gz' % (ud.module.replace('/', '.'), ud.host, ud.tag, ud.date, norecurse, fullpath), d)

        return os.path.join(data.getVar("DL_DIR", d, True), ud.localfile)

    def forcefetch(self, url, ud, d):
        if (ud.date == "now"):
            return True
        return False

    def go(self, loc, ud, d):

        method = ud.parm.get('method', 'pserver')
        localdir = ud.parm.get('localdir', ud.module)
        cvs_port = ud.parm.get('port', '')

        cvs_rsh = None
        if method == "ext":
            if "rsh" in ud.parm:
                cvs_rsh = ud.parm["rsh"]

        if method == "dir":
            cvsroot = ud.path
        else:
            cvsroot = ":" + method
            cvsproxyhost = data.getVar('CVS_PROXY_HOST', d, True)
            if cvsproxyhost:
                cvsroot += ";proxy=" + cvsproxyhost
            cvsproxyport = data.getVar('CVS_PROXY_PORT', d, True)
            if cvsproxyport:
                cvsroot += ";proxyport=" + cvsproxyport
            cvsroot += ":" + ud.user
            if ud.pswd:
                cvsroot += ":" + ud.pswd
            cvsroot += "@" + ud.host + ":" + cvs_port + ud.path

        options = []
        if 'norecurse' in ud.parm:
            options.append("-l")
        if ud.date:
            # treat YYYYMMDDHHMM specially for CVS
            if len(ud.date) == 12:
                options.append("-D \"%s %s:%s UTC\"" % (ud.date[0:8], ud.date[8:10], ud.date[10:12]))
            else:
                options.append("-D \"%s UTC\"" % ud.date)
        if ud.tag:
            options.append("-r %s" % ud.tag)

        localdata = data.createCopy(d)
        data.setVar('OVERRIDES', "cvs:%s" % data.getVar('OVERRIDES', localdata), localdata)
        data.update_data(localdata)

        data.setVar('CVSROOT', cvsroot, localdata)
        data.setVar('CVSCOOPTS', " ".join(options), localdata)
        data.setVar('CVSMODULE', ud.module, localdata)
        cvscmd = data.getVar('FETCHCOMMAND', localdata, 1)
        cvsupdatecmd = data.getVar('UPDATECOMMAND', localdata, 1)

        if cvs_rsh:
            cvscmd = "CVS_RSH=\"%s\" %s" % (cvs_rsh, cvscmd)
            cvsupdatecmd = "CVS_RSH=\"%s\" %s" % (cvs_rsh, cvsupdatecmd)

        # create module directory
        logger.debug(2, "Fetch: checking for module directory")
        pkg = data.expand('${PN}', d)
        pkgdir = os.path.join(data.expand('${CVSDIR}', localdata), pkg)
        moddir = os.path.join(pkgdir, localdir)
        if os.access(os.path.join(moddir, 'CVS'), os.R_OK):
            logger.info("Update " + loc)
            # update sources there
            os.chdir(moddir)
            myret = os.system(cvsupdatecmd)
        else:
            logger.info("Fetch " + loc)
            # check out sources there
            bb.utils.mkdirhier(pkgdir)
            os.chdir(pkgdir)
            logger.debug(1, "Running %s", cvscmd)
            myret = os.system(cvscmd)

        if myret != 0 or not os.access(moddir, os.R_OK):
            try:
                os.rmdir(moddir)
            except OSError:
                pass
            raise FetchError(ud.module)

        scmdata = ud.parm.get("scmdata", "")
        if scmdata == "keep":
            tar_flags = ""
        else:
            tar_flags = "--exclude 'CVS'"

        # tar them up to a defined filename
        if 'fullpath' in ud.parm:
            os.chdir(pkgdir)
            myret = os.system("tar %s -czf %s %s" % (tar_flags, ud.localpath, localdir))
        else:
            os.chdir(moddir)
            os.chdir('..')
            myret = os.system("tar %s -czf %s %s" % (tar_flags, ud.localpath, os.path.basename(moddir)))

        if myret != 0:
            try:
                os.unlink(ud.localpath)
            except OSError:
                pass
            raise FetchError(ud.module)
