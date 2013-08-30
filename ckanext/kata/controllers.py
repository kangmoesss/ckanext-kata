"""
Controllers for Kata plus some additional functions.
"""

import logging
import os
import tempfile
import urllib2
import subprocess

from _text import orngText
from paste.deploy.converters import asbool
from pylons import response, config, request, session, g
from pylons.decorators.cache import beaker_cache
from pylons.i18n import gettext as _
from rdflib.term import Identifier
from pairtree.storage_exceptions import FileNotFoundException
from sqlalchemy import func

from ckan.controllers.api import ApiController
from ckan.controllers.package import PackageController
from ckan.controllers.storage import get_ofs
from ckan.controllers.user import UserController
from ckan.controllers.admin import AdminController
from ckan.logic import check_access
from ckan.lib.munge import substitute_ascii_equivalents
from ckan.lib.base import BaseController, c, h, redirect, render
from ckan.lib.navl.dictization_functions import unflatten
from ckan.logic import get_action, clean_dict, tuplize_dict, parse_params
from ckan.model import Package, User, Related, Group, meta, Resource, PackageExtra
from ckan.model.authz import add_user_to_role
from ckanext.kata.model import KataAccessRequest
from ckanext.kata.urnhelper import URNHelper
from ckanext.kata.vocab import DC, FOAF, RDF, RDFS, XSD, Graph, URIRef, Literal
from ckanext.kata.utils import convert_to_text, send_contact_email
import ckan.model as model
import ckan.model.misc as misc
import ckan.lib.i18n

from operator import itemgetter

log = logging.getLogger('ckanext.kata.controller')

BUCKET = config.get('ckan.storage.bucket', 'default')


def get_extra_contact(context, data_dict, key="contact_name"):
    model = context['model']

    terms = data_dict.get('query') or data_dict.get('q') or []
    if isinstance(terms, basestring):
        terms = [terms]
    terms = [t.strip() for t in terms if t.strip()]

    if 'fields' in data_dict:
        log.warning('"fields" parameter is deprecated.  '
                    'Use the "query" parameter instead')

    offset = data_dict.get('offset')
    limit = data_dict.get('limit')

    # TODO: should we check for user authentication first?
    q = model.Session.query(model.PackageExtra)

    if not len(terms):
        return [], 0

    for term in terms:
        escaped_term = misc.escape_sql_like_special_characters(term, escape='\\')
        q = q.filter(model.PackageExtra.key.contains(key))
        q = q.filter(model.PackageExtra.value.ilike("%" + escaped_term + "%"))

    q = q.offset(offset)
    q = q.limit(limit)
    return q.all()

def get_discipline(context, data_dict):
    model = context['model']

    terms = data_dict.get('query') or data_dict.get('q') or []
    if isinstance(terms, basestring):
        terms = [terms]
    terms = [t.strip() for t in terms if t.strip()]

    if 'fields' in data_dict:
        log.warning('"fields" parameter is deprecated.  '
                    'Use the "query" parameter instead')

    offset = data_dict.get('offset')
    limit = data_dict.get('limit')

    # TODO: should we check for user authentication first?
    q = model.Session.query(model.Group)

    if not len(terms):
        return [], 0
    katagrp = Group.get('KATA')
    res = []
    for term in terms:
        escaped_term = misc.escape_sql_like_special_characters(term, escape='\\')
        for child in katagrp.get_children_groups():
            if escaped_term in child['name']:
                res.append(child)
    return res


class MetadataController(BaseController):

    def _make_rights_element(self, extras):
        '''
        Return license information as an RDF literal.

        :param extras:
        :return:
        '''

        xmlstr = ""
        if extras["access"] == 'contact':
            xmlstr = '<RightsDeclaration RIGHTSCATEGORY="COPYRIGHTED">' + extras['accessrequestURL'] + '</RightsDeclaration>'
        if extras["access"] in ('ident', 'free'):
            xmlstr = '<RightsDeclaration RIGHTSCATEGORY="LICENSED">' + extras['licenseURL'] + '</RightsDeclaration>'
        if extras["access"] == 'form':
            xmlstr = '<RightsDeclaration RIGHTSCATEGORY="CONTRACTUAL">' + extras['accessRights'] + '</RightsDeclaration>'
        return Literal(xmlstr, datatype=RDF.XMLLiteral)

    def _make_temporal(self, extras):
        dcmi_period = ""
        if all(k in extras for k in ("temporal_coverage_begin",
                                    "temporal_coverage_end")):
            dcmi_period = "start=%s; end=%s; scheme=ISO-8601;" % (extras["temporal_coverage_begin"],
                                                            extras["temporal_coverage_end"])
        return dcmi_period

    @beaker_cache(type="dbm", expire=604800)
    def urnexport(self):
        response.headers['Content-type'] = 'text/xml'
        return URNHelper.list_packages()

    def tordf(self, id, format):
        '''
        Get an RDF presentation of a package.

        :param id:
        :param format:
        :return:
        '''
        graph = Graph()
        pkg = Package.get(id)
        if pkg:
            data = pkg.as_dict()
            metadoc = URIRef('')
            user = None
            if pkg.roles:
                owner = [role for role in pkg.roles if role.role == 'admin']
                if len(owner):
                    user = User.get(owner[0].user_id)
            profileurl = ""
            if user:
                profileurl = URIRef(config.get('ckan.site_url', '') +\
                    h.url_for(controller="user", action="read", id=user.name))
            graph.add((metadoc, DC.identifier, Literal(data["id"])\
                                if 'identifier' not in data["extras"]\
                                else URIRef(data["extras"]["identifier"])))
            graph.add((metadoc, DC.modified, Literal(data["metadata_modified"],
                                                 datatype=XSD.dateTime)))
            graph.add((metadoc, FOAF.primaryTopic, Identifier(data['name'])))
            uri = URIRef(data['name'])
            if data["license"]:
                graph.add((uri, DC.rights, Literal(data["license"])))
            if "versionPID" in data["extras"]:
                graph.add((uri, DC.identifier, Literal(data["extras"]["versionPID"])))
            graph.add((uri, DC.identifier, Literal(data["name"])))
            graph.add((uri, DC.modified, Literal(data.get("version", ''),
                                                 datatype=XSD.dateTime)))
            org = URIRef(FOAF.Person)
            if profileurl:
                graph.add((uri, DC.publisher, profileurl))
                graph.add((profileurl, RDF.type, org))
                graph.add((profileurl, FOAF.name, Literal(data["extras"]["publisher"])))
                graph.add((profileurl, FOAF.phone, Identifier(data["extras"]["phone"])))
                graph.add((profileurl, FOAF.homepage, Identifier(data["extras"]["contactURL"])))
                graph.add((uri, DC.rightsHolder, URIRef(data["extras"]["owner"])
                                                if data["extras"]["owner"].startswith(('http','urn'))\
                                                else Literal(data["extras"]["owner"])))
            log.debug(data["extras"])
            if all((k in data["extras"] and data["extras"][k] != "") for k in ("project_name",\
                                                 "project_homepage",\
                                                 "project_funding",\
                                                 "funder")):
                project = URIRef(FOAF.Project)
                projecturl = URIRef(data["extras"]["project_homepage"])
                graph.add((uri, DC.contributor, projecturl))
                graph.add((projecturl, RDF.type, project))
                graph.add((projecturl, FOAF.name, Literal(data["extras"]["project_name"])))
                graph.add((projecturl, FOAF.homepage, Identifier(data["extras"]["project_homepage"])))
                graph.add((projecturl, RDFS.comment,
                            Literal(" ".join((data["extras"]["funder"],
                                              data["extras"]["project_funding"])))))
            for key in data["extras"]:
                log.debug(key)
                if key.startswith('author'):
                    graph.add((uri, DC.creator, URIRef(data["extras"][key])\
                                                if data["extras"][key].startswith(('http','urn'))\
                                                else Literal(data["extras"][key])))
                if key.startswith("title"):
                    lastlangnum = key.split('_')[-1]
                    log.debug(lastlangnum)
                    lastlang = data["extras"]["lang_title_%s" % lastlangnum]
                    graph.add((uri, DC.title, Literal(data["extras"][key],
                                        lang=lastlang)))
            for tag in data['tags']:
                graph.add((uri, DC.subject, Literal(tag)))
            for lang in data["extras"].get("language", "").split(','):
                graph.add((uri, DC.language, Literal(lang.strip())))
            if "access" in data["extras"]:
                graph.add((uri, DC.rights, self._make_rights_element(data["extras"])))

            # Extended metadatamodel

            if all(k in data["extras"] for k in ("temporal_coverage_begin",
                                                  "temporal_coverage_end")):
                graph.add((uri, DC.temporal, Literal(self._make_temporal(data["extras"]))))
            if "geographical_coverage" in data["extras"]:
                graph.add((uri, DC.spatial, Literal(data["extras"]["geographical_coverage"])))
            for rel in Related.get_for_dataset(pkg):
                graph.add((uri, DC.isReferencedBy, Literal(rel.related.title)))
            if "notes_rendered" in data:
                graph.add((uri, DC.description, Literal(data["notes_rendered"])))

            response.headers['Content-type'] = 'text/xml'
            if format == 'rdf':
                format = 'pretty-xml'
            return graph.serialize(format=format)
        else:
            return ""


class KATAApiController(ApiController):

    def author_autocomplete(self):
        pass

    def organization_autocomplete(self):
        pass

    def contact_autocomplete(self):
        q = request.params.get('incomplete', '')
        limit = request.params.get('limit', 10)
        tag_names = []
        if q:
            context = {'model': model, 'session': model.Session,
                       'user': c.user or c.author}

            data_dict = {'q': q, 'limit': limit}

            tag_names = get_extra_contact(context, data_dict)

        tag_names = [k.value for k in tag_names]
        resultSet = {
            'ResultSet': {
                'Result': [{'Name': tag} for tag in tag_names]
            }
        }
        return self._finish_ok(resultSet)

    def discipline_autocomplete(self):
        q = request.params.get('incomplete', '')
        limit = request.params.get('limit', 10)
        tag_names = []
        if q:
            context = {'model': model, 'session': model.Session,
                       'user': c.user or c.author}

            data_dict = {'q': q, 'limit': limit}

            tag_names = get_discipline(context, data_dict)

        tag_names = [k['name'] for k in tag_names]
        resultSet = {
            'ResultSet': {
                'Result': [{'Name': tag} for tag in tag_names]
            }
        }
        return self._finish_ok(resultSet)

    def owner_autocomplete(self):
        q = request.params.get('incomplete', '')
        limit = request.params.get('limit', 10)
        tag_names = []
        if q:
            context = {'model': model, 'session': model.Session,
                       'user': c.user or c.author}

            data_dict = {'q': q, 'limit': limit}

            tag_names = get_extra_contact(context, data_dict, key="owner_name")

        tag_names = [k.value for k in tag_names]
        resultSet = {
            'ResultSet': {
                'Result': [{'Name': tag} for tag in tag_names]
            }
        }
        return self._finish_ok(resultSet)


class AccessRequestController(BaseController):

    def create_request(self, pkg_id):
        pkg = Package.get(pkg_id)
        user = c.userobj if c.userobj else None
        if user:
            req = KataAccessRequest(user.id, pkg.id)
            req.save()
            url = h.url_for(controller='package', action='read', id=pkg_id)
            h.flash_success(_("You now requested editor rights to package %s" % pkg.name))
            redirect(url)
        else:
            url = h.url_for(controller='package', action='read', id=pkg_id)
            h.flash_error(_("Please log in!"))
            redirect(url)

    def unlock_access(self, id):
        q = model.Session.query(KataAccessRequest)
        q = q.filter_by(id=id)
        req = q.first()
        if req:
            user = User.get(req.user_id)
            pkg = Package.get(req.pkg_id)
            add_user_to_role(user, 'editor', pkg)
            url = h.url_for(controller='package', action='read', id=req.pkg_id)
            h.flash_success(_("%s now has editor rights to package %s" % (user.name, pkg.name)))
            req.delete()
            meta.Session.commit()
            redirect(url)
        else:
            h.flash_error(_("No such request found!"))
            redirect('/')


class DataMiningController(BaseController):
    """
    Controller for scraping metadata content from files.
    """

    def read_data(self, id, resource_id):
        """
        Scrape all words from a file and save it to extras.
        """
        res = Resource.get(resource_id)
        pkg = Package.get(id)
        c.pkg_dict = pkg.as_dict()
        c.package = pkg
        c.resource = get_action('resource_show')({'model': model},
                                                     {'id': resource_id})
        label = res.url.split(config.get('ckan.site_url') + '/storage/f/')[-1]
        label = urllib2.unquote(label)
        ofs = get_ofs()

        try:
            # Get file location
            furl = ofs.get_url(BUCKET, label).split('file://')[-1]
        except FileNotFoundException:
            h.flash_error(_('Cannot do data mining on remote resource!'))
            url = h.url_for(controller='package', action='resource_read',
                            id=id, resource_id=resource_id)
            return redirect(url)

        wordstats = {}
        ret = {}

        if res.format in ('TXT', 'txt'):
            wdsf, wdspath = tempfile.mkstemp()
            os.write(wdsf, "%s\nmetadata description title information" % furl)

            with os.fdopen(wdsf, 'r') as wordfile:
                preproc = orngText.Preprocess()
                table = orngText.loadFromListWithCategories(wdspath)
                data = orngText.bagOfWords(table, preprocessor=preproc)
                words = orngText.extractWordNGram(data, threshold=10.0, measure='MI')

            for i in range(len(words)):
                d = words[i]
                wordstats = d.get_metas(str)

            for k, v in wordstats.items():
                if v.value > 10.0:
                    ret[unicode(k, 'utf8')] = v.value

            c.data_tags = sorted(ret.iteritems(), key=itemgetter(1), reverse=True)[:30]
            os.remove(wdspath)

            for i in range(len(data)):
                    d = words[i]
                    wordstats = d.get_metas(str)

            words = []
            for k, v in wordstats.items():
                words.append(k)

            # Save scraped words to extras.

            model.repo.new_revision()
            if not 'autoextracted_description' in pkg.extras:
                pkg.extras['autoextracted_description'] = ' '.join(words)

            pkg.save()

            return render('datamining/read.html')

        elif res.format in ('odt', 'doc', 'xls', 'ods', 'odp', 'ppt', 'doc', 'html'):

            textfd, textpath = convert_to_text(res, furl)

            if not textpath:
                h.flash_error(_('This file could not be mined for any data!'))
                os.close(textfd)
                return render('datamining/read.html')
            else:
                wdsf, wdspath = tempfile.mkstemp()
                os.write(wdsf, "%s\nmetadata description title information" % textpath)
                preproc = orngText.Preprocess()
                table = orngText.loadFromListWithCategories(wdspath)
                data = orngText.bagOfWords(table, preprocessor=preproc)
                words = orngText.extractWordNGram(data, threshold=10.0, measure='MI')

                for i in range(len(words)):
                    d = words[i]
                    wordstats = d.get_metas(str)

                for k, v in wordstats.items():
                    if v.value > 10.0:
                        ret[unicode(k, 'utf8')] = v.value

                c.data_tags = sorted(ret.iteritems(), key=itemgetter(1), reverse=True)[:30]
                os.close(textfd)
                os.close(wdsf)
                os.remove(wdspath)
                os.remove(textpath)

                for i in range(len(data)):
                    d = words[i]
                    wordstats = d.get_metas(str)

                words = []

                for k, v in wordstats.items():
                    log.debug(k)
                    words.append(substitute_ascii_equivalents(k))

                model.repo.new_revision()

                if not 'autoextracted_description' in pkg.extras:
                    pkg.extras['autoextracted_description'] = ' '.join(words)

                pkg.save()

                return render('datamining/read.html')
        else:
            h.flash_error(_('This metadata document is not in proper format for data mining!'))
            url = h.url_for(controller='package', action='resource_read',
                            id=id, resource_id=resource_id)
            return redirect(url)

    def save(self):
        if not c.user:
            return

        model.repo.new_revision()
        data = clean_dict(unflatten(tuplize_dict(parse_params(request.params))))
        package = Package.get(data['pkgid'])
        keywords = []
        context = {'model': model, 'session': model.Session,
                   'user': c.user}

        if check_access('package_update', context, data_dict={"id": data['pkgid']}):

            for k, v in data.items():
                if k.startswith('kw'):
                    keywords.append(v)

            tags = package.get_tags()

            for kw in keywords:
                if not kw in tags:
                    package.add_tag_by_name(kw)

            package.save()
            url = h.url_for(controller='package', action='read', id=data['pkgid'])
            redirect(url)
        else:
            redirect('/')


class ContactController(BaseController):
    """
    Add features to contact the dataset's owner. 
    
    From the web page, this can be seen from the link telling that this dataset is accessible by contacting the author. 
    The feature provides a form for message sending, and the message is sent via e-mail. 
    """

    def send(self, pkg_id):
        """
        Send a contact e-mail if allowed.
        """
        
        package = Package.get(pkg_id)
        url = h.url_for(controller='package',
                action="read",
                id=package.id)
        if c.user:
                userid = None
                for role in package.roles:
                    if role.role == "admin":
                        userid = role.user_id
                        break
                if userid:
                    owner = User.get(userid)
                    msg = request.params.get('msg', '')
                    if msg:
                        model.repo.new_revision()

                        send_contact_email(owner, c.userobj, package, \
                                           msg)

                        # Mark this user as contacted
                        if "contacted" in c.userobj.extras:
                            c.userobj.extras['contacted'].append(pkg_id)
                        else:
                            c.userobj.extras['contacted'] = []
                            c.userobj.extras['contacted'].append(pkg_id)
                        c.userobj.save()

                    else:
                        h.flash_error(_("No message"))
                        return redirect(url)
                else:
                    h.flash_error(_("No owner found"))
                    return redirect(url)
                h.flash_notice(_("Message sent"))
        else:
            h.flash_error(_("Please login"))
        return redirect(url)


    def render(self, pkg_id):
        """
        Render the contact form if allowed.
        """
        
        c.package = Package.get(pkg_id)
        url = h.url_for(controller='package',
                        action="read",
                        id=c.package.id)
        if c.user:
            if pkg_id not in c.userobj.extras.get('contacted', []):
                return render('contact/contact_form.html')
            else:
                h.flash_error(_("Already contacted"))
                return redirect(url)
        else:
            h.flash_error(_("Please login"))
            return redirect(url)

class KataUserController(UserController):
    """
    Overwrite logged_in function in super class.
    """
    def logged_in(self):
        """
        Redirect user to own profile page instead of dashboard.
        @return - some sort of redirect object??
        """
        # we need to set the language via a redirect
        lang = session.pop('lang', None)
        session.save()
        came_from = request.params.get('came_from', '')

        # we need to set the language explicitly here or the flash
        # messages will not be translated.
        ckan.lib.i18n.set_lang(lang)

        if c.user:
            context = {'model': model,
                   'user': c.user}

            data_dict = {'id': c.user}

            user_dict = get_action('user_show')(context, data_dict)

            h.flash_success(_("%s is now logged in") %
                        user_dict['display_name'])
            if came_from:
                return h.redirect_to(str(came_from))
            return h.redirect_to(controller='user', action='read', id=c.userobj.name)
        else:
            err = _('Login failed. Bad username or password.')
            if g.openid_enabled:
                err += _(' (Or if using OpenID, it hasn\'t been associated '
                     'with a user account.)')
            if asbool(config.get('ckan.legacy_templates', 'false')):
                h.flash_error(err)
                h.redirect_to(locale=lang, controller='user',
                          action='login', came_from=came_from)
            else:
                return self.login(error=err)

class KataPackageController(PackageController):
    """
    Adds advanced search feature.
    """
    def advanced_search(self):
        """
        Parse query parameters from different search form inputs, modify into
        one query string 'q' in the context and call basic search() method of
        the super class.

        @return - dictionary with keys results and count
        """
        # parse author search into q
        q_author = c.q_author = request.params.get('q_author', u'')

        # unicode format (decoded from utf8)
        q_free = c.q_free = request.params.get('q_free', u'')
        q = c.q = q_free + u' AND '+ u'author:' +  q_author

        log.debug('advanced_search(): request.params.items(): %r' % request.params.items())
        #log.debug('advanced_search(): q: %r' % q)
        log.debug('advanced_search(): call to search()')
        return self.search()
    
class KataInfoController(BaseController):
    """
    Renders help page.
    """
    def render_help(self):
        return render('kata/help.html')
    def render_faq(self):
        return render('kata/faq.html')
    
class SystemController(AdminController):
    def system(self):
        """
        Generates a simple page about very basic system information
        to admin site
        """
        smem = subprocess.Popen(["free", "-m"], stdout=subprocess.PIPE).communicate()[0]
        c.mem = smem.split( );
        # Add empty list items for empty cells to keep template clean
        c.mem.extend(['','',''])
        c.mem.insert(0, '')
        c.mem = c.mem[0:18] + ['','',''] + c.mem[-7:]
        
        shd = subprocess.Popen(["df", "-h"], stdout=subprocess.PIPE).communicate()[0]
        c.hd = shd.split( );
        # Split matches the single phrase "Mounted on", quick fix:
        c.hd[5] = c.hd[5] + ' ' + c.hd[6]
        del c.hd[6]
        
        sut = subprocess.Popen(["uptime"], stdout=subprocess.PIPE).communicate()[0]
        c.ut = sut.split(',');
        del c.ut[1:2]
        c.ut[2] = c.ut[2] + ', ' + c.ut[3] + ', '+ c.ut[4]
        del c.ut[3:]
        
        return render('admin/system.html')

    def report(self):
        """
        Generates a simple report page to admin site
        """
        # package info
        c.numpackages = c.openpackages = 0
        c.numpackages = model.Session.query(Package.id).count()
        key = 'access'
        value = 'free'
        c.openpackages = model.Session.query(Package.id).\
                   filter(PackageExtra.key==key).\
                   filter(PackageExtra.value==value).\
                   filter(Package.id==PackageExtra.package_id).\
                   count()
        # format to: d.dd %
        c.popen = float(c.openpackages) / float(c.numpackages) * 100
        c.popen = "{0:.2f}".format(c.popen) + ' %'
        
        # user info
        c.numusers = 0
        c.numusers = model.Session.query(User.id).count()
        
        return render('admin/report.html')
    